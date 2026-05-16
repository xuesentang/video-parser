"""博主追踪系统 - 报告生成核心逻辑
手动触发报告生成，分批次反爬策略
AI概要：批量调用，基于标题扩展50字左右
"""

import logging
import random
import time
from datetime import datetime, timezone, timedelta

from tracker_database import (
    get_user_subscribed_creators,
    create_report,
    update_report_content,
    fail_report,
    update_creator_checked,
    update_report_progress,
)
from tracker_bilibili_adapter import (
    get_recent_videos as bilibili_get_videos,
    _init_session as bilibili_refresh_session,
)
from tracker_youtube_adapter import (
    get_recent_videos as youtube_get_videos,
)

logger = logging.getLogger("tracker_scheduler")

BATCH_SIZE = 5  # 增大批次（3→5）
BATCH_PAUSE_MIN = 3.0  # 缩短批次间隔（5→3）
BATCH_PAUSE_MAX = 5.0  # 缩短批次间隔（10→5）
CREATOR_PAUSE_MIN = 1.0  # 缩短博主间间隔（2→1）
CREATOR_PAUSE_MAX = 2.0  # 缩短博主间间隔（4→2）
BILIBILI_SESSION_REFRESH_INTERVAL = 5  # Cookie自动生成后，刷新需求降低（3→5）
REPORT_TIME_RANGE_HOURS = 72


def _jitter_sleep(min_sec: float, max_sec: float, label: str = ""):
    """带随机抖动的等待，避免请求模式过于规律被平台识别"""
    wait = random.uniform(min_sec, max_sec)
    if label:
        logger.debug("%s 等待 %.1fs", label, wait)
    time.sleep(wait)


def _batch_generate_summaries(videos: list) -> dict[str, str]:
    """
    批量为视频生成AI概要（1次API调用处理所有视频）
    每个视频50字左右，基于标题扩展
    失败时重试1次，再失败则降级为原始描述
    """
    if not videos:
        return {}

    video_list_text = ""
    for i, v in enumerate(videos, 1):
        desc_short = (v.description or "")[:100]
        video_list_text += f"{i}. 标题：{v.title}"
        if desc_short:
            video_list_text += f"  描述：{desc_short}"
        video_list_text += "\n"

    prompt = (
        f"请为以下{len(videos)}个视频分别生成50字左右的扩展概要，"
        f"补充视频可能涉及的内容要点。\n"
        f"严格按以下格式输出，每个视频一行，用编号对应：\n"
        f"1. 概要内容\n2. 概要内容\n...\n\n"
        f"视频列表：\n{video_list_text}"
    )

    messages = [
        {"role": "system", "content": "你是一个视频内容概括助手，擅长根据标题快速扩展视频内容概要。"},
        {"role": "user", "content": prompt},
    ]

    for attempt in range(2):
        try:
            from summarizer import VideoSummarizer
            summarizer = VideoSummarizer()
            response = summarizer.client.chat.completions.create(
                model=summarizer.model,
                messages=messages,
                stream=False,
                temperature=0.5,
                max_tokens=200 * len(videos),
            )
            result_text = response.choices[0].message.content.strip()
            return _parse_batch_result(result_text, videos)
        except Exception as e:
            logger.warning("批量AI概要生成失败(第%d次): %s", attempt + 1, e)
            if attempt == 0:
                time.sleep(5)

    logger.warning("批量AI概要生成全部失败，降级为原始描述")
    return {v.video_id: (v.description[:100] if v.description else v.title) for v in videos}


def _parse_batch_result(result_text: str, videos: list) -> dict[str, str]:
    """解析批量AI返回的结果，按编号映射到video_id"""
    summaries = {}
    lines = result_text.strip().split("\n")

    for i, v in enumerate(videos):
        expected_prefix = f"{i + 1}."
        matched_line = None

        for line in lines:
            line = line.strip()
            if line.startswith(expected_prefix):
                matched_line = line[len(expected_prefix):].strip()
                break

        if matched_line:
            summaries[v.video_id] = matched_line
        else:
            summaries[v.video_id] = v.description[:100] if v.description else v.title

    return summaries


def _videos_to_markdown_section(
    creator_name: str,
    platform: str,
    videos: list,
    summaries: dict[str, str],
) -> str:
    """将一个博主的视频列表转为Markdown片段，无视频时返回空字符串"""
    if not videos:
        return ""

    platform_label = "B站" if platform == "bilibili" else "YouTube"
    lines = [f"### {creator_name}（{platform_label}）\n"]
    for v in videos:
        summary = summaries.get(v.video_id, v.description[:100] if v.description else "")
        lines.append(f"**{v.title}**")
        lines.append(f"- 链接：{v.url}")
        lines.append(f"- 发布时间：{_format_time(v.published_at)}")
        if v.view_count:
            lines.append(f"- 播放量：{v.view_count}")
        lines.append(f"- AI概要：{summary}")
        lines.append("")

    return "\n".join(lines)


def _format_time(iso_str: str) -> str:
    """格式化ISO时间为可读格式"""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


def generate_report_for_user(user_id: int, report_id: int = None) -> int:
    """
    为指定用户生成追踪报告，返回报告ID

    核心策略：
    1. 分批次处理博主（每批BATCH_SIZE个），批次间暂停
    2. 博主间带随机抖动的等待
    3. B站定期刷新Session
    4. 每个博主的视频批量调用AI生成概要（1次API调用）
    5. 实时更新进度到数据库（供前端轮询）
    6. 无视频时返回提示而非空报告

    Args:
        user_id: 用户ID
        report_id: 可选，传入已创建的报告ID（由API层传入，确保前后端使用同一ID）
                  如果不传，则内部创建新报告（兼容旧调用）
    """
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    if report_id is None:
        report = create_report(user_id, today)
        report_id = report["id"]
    else:
        # 使用传入的report_id，更新报告日期
        from tracker_database import get_report_by_id
        report = get_report_by_id(report_id, user_id)
        if not report:
            logger.error("报告不存在 report_id=%d user_id=%d", report_id, user_id)
            return report_id

    try:
        creators = get_user_subscribed_creators(user_id)
        total_creators = len(creators)

        if not creators:
            update_report_content(
                report_id,
                content_markdown="",
                video_count=0,
                status="no_subscription",
            )
            return report_id

        all_sections = []
        total_videos = 0
        errors = []

        for idx, creator in enumerate(creators):
            platform = creator["platform"]
            platform_id = creator["platform_id"]
            name = creator["name"]

            update_report_progress(
                report_id,
                current=idx + 1,
                total=total_creators,
                current_creator=name,
            )

            if idx > 0 and idx % BATCH_SIZE == 0:
                logger.info(
                    "批次暂停：已处理 %d/%d 个博主",
                    idx, total_creators,
                )
                _jitter_sleep(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX, "批次间")

            if idx > 0:
                _jitter_sleep(CREATOR_PAUSE_MIN, CREATOR_PAUSE_MAX, "博主间")

            try:
                if platform == "bilibili":
                    if idx > 0 and idx % BILIBILI_SESSION_REFRESH_INTERVAL == 0:
                        logger.info("刷新B站Session (第%d个博主)", idx + 1)
                        bilibili_refresh_session()
                    videos = bilibili_get_videos(platform_id, hours=REPORT_TIME_RANGE_HOURS, creator_name=name)
                elif platform == "youtube":
                    videos = youtube_get_videos(platform_id, hours=REPORT_TIME_RANGE_HOURS)
                else:
                    continue

                update_creator_checked(creator["id"])

                summaries = _batch_generate_summaries(videos)

                total_videos += len(videos)
                section = _videos_to_markdown_section(name, platform, videos, summaries)
                if section:
                    all_sections.append(section)

            except Exception as e:
                logger.error("获取博主视频失败 name=%s: %s", name, e)
                errors.append(f"{name}（获取失败: {str(e)[:80]}）")

        if total_videos == 0:
            update_report_content(
                report_id,
                content_markdown="",
                video_count=0,
                status="no_videos",
            )
            return report_id

        markdown = f"# 博主追踪报告 - {today}\n\n"
        markdown += f"追踪博主数：{total_creators} | 发现新视频：{total_videos}\n\n---\n\n"
        markdown += "\n".join(all_sections)

        if errors:
            markdown += "\n### 获取失败\n\n"
            for err in errors:
                markdown += f"- {err}\n"

        update_report_content(
            report_id,
            content_markdown=markdown,
            video_count=total_videos,
            status="completed",
        )

    except Exception as e:
        logger.error("报告生成失败 user_id=%d: %s", user_id, e)
        fail_report(report_id, str(e)[:200])

    return report_id
