"""YouTube频道适配器 - yt-dlp备用方案
当RSS方式失败时自动降级使用
复用 tracker_youtube_adapter 的数据结构，确保接口完全兼容
"""

import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import yt_dlp

from tracker_youtube_adapter import CreatorInfo, VideoItem

logger = logging.getLogger("tracker_youtube_ytdlp")


def is_youtube_channel_url(url: str) -> bool:
    """判断是否为YouTube频道链接（与原有模块保持一致）"""
    try:
        host = urlparse(url).netloc.lower()
        return "youtube.com" in host and (
            "/channel/" in url or "/c/" in url or "/@" in url
        )
    except Exception:
        return False


def get_creator_info(url: str) -> CreatorInfo:
    """
    使用yt-dlp获取YouTube频道信息
    作为RSS方式的备用方案
    """
    if not is_youtube_channel_url(url):
        raise ValueError("无效的YouTube频道链接")

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'playlistend': 1,  # 只获取频道信息，不需要视频列表
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # 提取channel_id
            channel_id = info.get('channel_id', '')
            if not channel_id and 'id' in info:
                # 有些URL类型返回的id就是channel_id
                channel_id = info.get('id', '')

            # 提取频道名称
            name = info.get('channel', info.get('uploader', '未知频道'))

            # 提取头像
            avatar_url = ''
            thumbnails = info.get('thumbnails', [])
            if thumbnails and len(thumbnails) > 0:
                avatar_url = thumbnails[0].get('url', '')

            # 提取简介
            description = info.get('description', '')[:200]

            # 构建主页链接
            home_url = info.get('channel_url', info.get('webpage_url', url))

            return CreatorInfo(
                platform="youtube",
                platform_id=channel_id,
                name=name,
                avatar_url=avatar_url,
                description=description,
                home_url=home_url,
            )

    except Exception as e:
        logger.error("yt-dlp获取YouTube频道信息失败: %s", e)
        raise ValueError(f"获取YouTube频道信息失败: {e}")


def get_recent_videos(channel_id: str, hours: int = 72) -> list[VideoItem]:
    """
    使用yt-dlp获取频道近期视频列表
    作为RSS方式的备用方案
    """
    if not channel_id:
        raise ValueError("channel_id不能为空")

    # 构建频道URL
    channel_url = f"https://www.youtube.com/channel/{channel_id}"

    # 计算时间 cutoff
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    ydl_opts = {
        'quiet': True,
        'extract_flat': False,  # 需要完整信息包括发布时间
        'skip_download': True,
        'playlistend': 50,  # 最多获取50个视频
    }

    videos = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

            entries = info.get('entries', [])
            if not entries:
                logger.warning("yt-dlp未获取到任何视频: %s", channel_id)
                return videos

            for entry in entries:
                if not entry:
                    continue

                # 提取发布时间
                upload_date_str = entry.get('upload_date', '')  # 格式: YYYYMMDD
                published_at = _parse_upload_date(upload_date_str)

                # 过滤时间范围
                if published_at and published_at < cutoff:
                    continue

                video_id = entry.get('id', '')
                title = entry.get('title', '未知标题')

                # 构建视频URL
                url = entry.get('webpage_url', f"https://www.youtube.com/watch?v={video_id}")

                # 提取缩略图
                thumbnail = ''
                thumbnails = entry.get('thumbnails', [])
                if thumbnails and len(thumbnails) > 0:
                    thumbnail = thumbnails[-1].get('url', '')  # 取最高分辨率

                # 提取时长（秒）
                duration = entry.get('duration', 0) or 0

                # 提取播放量
                view_count = entry.get('view_count', 0) or 0

                # 提取简介
                description = entry.get('description', '')[:200]

                videos.append(VideoItem(
                    video_id=video_id,
                    title=title,
                    url=url,
                    published_at=published_at.isoformat() if published_at else datetime.now(timezone.utc).isoformat(),
                    duration=int(duration),
                    thumbnail=thumbnail,
                    view_count=int(view_count),
                    description=description,
                ))

    except Exception as e:
        logger.error("yt-dlp获取YouTube视频列表失败: %s", e)
        raise ValueError(f"获取视频列表失败: {e}")

    logger.info("yt-dlp成功获取 %d 个视频 (channel_id=%s)", len(videos), channel_id)
    return videos


def _parse_upload_date(date_str: str) -> datetime | None:
    """解析yt-dlp的upload_date格式 (YYYYMMDD)"""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return datetime(
            int(date_str[:4]),
            int(date_str[4:6]),
            int(date_str[6:8]),
            tzinfo=timezone.utc
        )
    except ValueError:
        return None