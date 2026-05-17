import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import yt_dlp

from config import PROXY_URL, get_ydl_cookie_option, get_ydl_runtime_options
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
        **get_ydl_runtime_options(),
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'playlistend': 1,
    }
    if PROXY_URL:
        ydl_opts['proxy'] = PROXY_URL
    ydl_opts.update(get_ydl_cookie_option())

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

    # 使用频道的 /videos 页面获取视频列表
    channel_videos_url = f"{channel_url}/videos"

    ydl_opts = {
        **get_ydl_runtime_options(),
        'quiet': True,
        'extract_flat': False,
        'skip_download': True,
        'playlistend': 50,
        'ignoreerrors': True,
        'no_warnings': True,
    }
    if PROXY_URL:
        ydl_opts['proxy'] = PROXY_URL
    ydl_opts.update(get_ydl_cookie_option())

    videos = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_videos_url, download=False)

            entries = info.get('entries', [])
            if not entries:
                logger.warning("yt-dlp未获取到任何视频: %s", channel_id)
                return videos

            for entry in entries:
                if not entry:
                    continue

                # 过滤非视频条目（如频道导航标签）
                entry_type = entry.get('_type', '')
                if entry_type == 'url' and not entry.get('id', '').startswith('UC'):
                    # 可能是导航链接，跳过
                    pass

                video_id = entry.get('id', '')
                title = entry.get('title', '未知标题')

                # 跳过频道导航标签
                if title in ('Videos', 'Shorts', 'Live', 'Playlists', 'Community', 'Channels', 'About'):
                    logger.debug("跳过频道导航标签: %s", title)
                    continue

                # 跳过没有有效video_id的条目
                if not video_id or len(video_id) != 11:
                    logger.debug("跳过无效video_id条目: %s", title)
                    continue

                # 提取发布时间
                upload_date_str = entry.get('upload_date', '')  # 格式: YYYYMMDD
                published_at = _parse_upload_date(upload_date_str)

                # 如果没有upload_date，尝试从webpage_url提取
                if not published_at:
                    # 有些条目可能没有upload_date，尝试其他方式
                    logger.debug("条目无upload_date: %s", title)
                    continue

                # 过滤时间范围
                if published_at and published_at < cutoff:
                    continue

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
    """解析yt-dlp的upload_date格式 (YYYYMMDD)

    注意：yt-dlp只返回日期（没有时分秒），为了不过滤掉当天发布的视频，
    我们将时间设为当天的 23:59:59 UTC。
    """
    if not date_str or len(date_str) != 8:
        return None
    try:
        return datetime(
            int(date_str[:4]),
            int(date_str[4:6]),
            int(date_str[6:8]),
            23, 59, 59,  # 设为当天最后一秒，避免当天视频被过滤
            tzinfo=timezone.utc
        )
    except ValueError:
        return None