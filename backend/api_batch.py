"""批量字幕提取 API 路由（独立模块，通过 include_router 挂载）
零AI调用，仅提取字幕文本，SSE流式返回每个视频的结果
"""

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from auth import get_current_user
from database import check_and_increment_usage, NORMAL_USER_USAGE_LIMIT

logger = logging.getLogger("api_batch")

router = APIRouter(prefix="/api", tags=["批量字幕"])

MAX_URLS = 20
VIDEO_PAUSE_MIN = 2.0
VIDEO_PAUSE_MAX = 3.0


class BatchSubtitleRequest(BaseModel):
    urls: list[str]


def _get_extractor():
    from summarizer import SubtitleExtractor
    if not hasattr(_get_extractor, "_instance"):
        _get_extractor._instance = SubtitleExtractor()
    return _get_extractor._instance


def _detect_platform(url: str) -> str:
    if "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "douyin.com" in url or "iesdouyin.com" in url:
        return "douyin"
    return "other"


@router.post("/batch-subtitles", response_class=EventSourceResponse)
async def batch_subtitles(
    req: BatchSubtitleRequest,
    user: dict = Depends(get_current_user),
) -> AsyncIterable[ServerSentEvent]:
    """
    批量提取视频字幕（SSE流式）
    事件类型: progress / result / error / done
    """
    if not req.urls:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": "请输入至少一个视频链接"}, ensure_ascii=False),
            event="error",
        )
        return

    if len(req.urls) > MAX_URLS:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": f"最多支持{MAX_URLS}个链接，当前{len(req.urls)}个"}, ensure_ascii=False),
            event="error",
        )
        return

    allowed, remaining = check_and_increment_usage(user["id"])
    if not allowed:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": f"使用额度已用完（共{NORMAL_USER_USAGE_LIMIT}次），升级VIP可无限使用", "need_vip": True}, ensure_ascii=False),
            event="error",
        )
        return

    extractor = _get_extractor()
    loop = asyncio.get_event_loop()
    total = len(req.urls)
    success_count = 0
    failed_count = 0

    for i, url in enumerate(req.urls):
        url = url.strip()
        if not url:
            continue

        yield ServerSentEvent(
            raw_data=json.dumps({"current": i + 1, "total": total, "url": url}, ensure_ascii=False),
            event="progress",
        )

        if i > 0:
            wait = random.uniform(VIDEO_PAUSE_MIN, VIDEO_PAUSE_MAX)
            await asyncio.sleep(wait)

        try:
            subtitle_data = await loop.run_in_executor(
                None, extractor.extract, url
            )

            platform = _detect_platform(url)
            title = subtitle_data.get("language", "")

            yield ServerSentEvent(
                raw_data=json.dumps({
                    "url": url,
                    "title": title,
                    "platform": platform,
                    "subtitle": subtitle_data,
                }, ensure_ascii=False),
                event="result",
            )
            success_count += 1

        except Exception as e:
            logger.warning("批量字幕提取失败 url=%s: %s", url, e)
            yield ServerSentEvent(
                raw_data=json.dumps({"url": url, "message": f"字幕提取失败: {str(e)[:100]}"}, ensure_ascii=False),
                event="error",
            )
            failed_count += 1

    yield ServerSentEvent(
        raw_data=json.dumps({"total": total, "success": success_count, "failed": failed_count, "remaining": remaining}, ensure_ascii=False),
        event="done",
    )
