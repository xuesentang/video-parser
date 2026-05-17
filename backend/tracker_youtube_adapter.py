import re
import time
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs

import httpx

from config import PROXY_URL

logger = logging.getLogger("tracker_youtube")

_PROXY_URL = PROXY_URL

# YouTube RSS 端点
YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml"

# 从URL中提取channel_id的正则
_CHANNEL_ID_PATTERN = re.compile(r"channel/(UC[a-zA-Z0-9_-]{22})")
_CHANNEL_CUSTOM_PATTERN = re.compile(r"youtube\.com/(c|@)([\w.-]+)")


@dataclass
class VideoItem:
    """标准化视频条目"""
    video_id: str
    title: str
    url: str
    published_at: str  # ISO 8601
    duration: int      # 秒（RSS不提供，默认0）
    thumbnail: str
    view_count: int    # RSS不提供，默认0
    description: str


@dataclass
class CreatorInfo:
    """标准化博主信息"""
    platform: str = "youtube"
    platform_id: str = ""   # channel_id
    name: str = ""
    avatar_url: str = ""
    description: str = ""
    home_url: str = ""


def is_youtube_channel_url(url: str) -> bool:
    """判断是否为YouTube频道链接"""
    try:
        host = urlparse(url).netloc.lower()
        return "youtube.com" in host and (
            "/channel/" in url or "/c/" in url or "/@" in url
        )
    except Exception:
        return False


def extract_channel_id_from_url(url: str) -> Optional[str]:
    """从YouTube频道URL中提取channel_id"""
    m = _CHANNEL_ID_PATTERN.search(url)
    if m:
        return m.group(1)
    return None


def _resolve_custom_url(url: str) -> Optional[str]:
    """
    解析自定义URL（@username 或 /c/name）为channel_id
    通过请求YouTube页面HTML提取channel_id
    """
    try:
        transport_kwargs = {}
        if _PROXY_URL:
            transport_kwargs["proxy"] = _PROXY_URL

        with httpx.Client(timeout=15, follow_redirects=True, **transport_kwargs) as client:
            resp = client.get(url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            })
            html = resp.text

            # 从HTML中提取channel_id
            # 方法1: meta标签
            m = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', html)
            if m:
                return m.group(1)

            # 方法2: 外部链接
            m = re.search(r'externalId.*?"(UC[a-zA-Z0-9_-]{22})"', html)
            if m:
                return m.group(1)

            # 方法3: RSS链接
            m = re.search(r'channel_id=(UC[a-zA-Z0-9_-]{22})', html)
            if m:
                return m.group(1)

            return None
    except Exception as e:
        logger.error("解析YouTube自定义URL失败: %s", e)
        return None


def get_creator_info(url: str) -> CreatorInfo:
    """
    输入YouTube频道URL，返回博主信息。
    支持格式:
      - https://www.youtube.com/channel/UCxxxxxx
      - https://www.youtube.com/@username
      - https://www.youtube.com/c/name
    """
    # 尝试直接提取channel_id
    channel_id = extract_channel_id_from_url(url)

    if not channel_id:
        # 自定义URL需要先解析
        channel_id = _resolve_custom_url(url)
        if not channel_id:
            raise ValueError(
                "无法从URL中提取YouTube频道ID，"
                "请输入标准频道链接（如 youtube.com/channel/UCxxxxxx）"
            )

    # 通过RSS获取频道信息
    import feedparser

    try:
        rss_url = f"{YOUTUBE_RSS_URL}?channel_id={channel_id}"

        transport_kwargs = {}
        if _PROXY_URL:
            transport_kwargs["proxy"] = _PROXY_URL

        # 先下载RSS内容
        with httpx.Client(timeout=15, follow_redirects=True, **transport_kwargs) as client:
            resp = client.get(rss_url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            })
            resp.raise_for_status()

        # 用feedparser解析
        feed = feedparser.parse(resp.text)

        if not feed.feed:
            raise ValueError("无法获取YouTube频道信息，请检查频道ID或网络代理配置")

        feed_info = feed.feed
        name = feed_info.get("title", "未知频道")
        home_url = feed_info.get("link", f"https://www.youtube.com/channel/{channel_id}")

        # 提取头像（从media_thumbnail或author_detail）
        avatar_url = ""
        if hasattr(feed_info, "media_thumbnail"):
            thumbnails = feed_info.media_thumbnail
            if thumbnails and len(thumbnails) > 0:
                avatar_url = thumbnails[0].get("url", "")

        # 提取简介
        description = feed_info.get("subtitle", "")[:200]

        return CreatorInfo(
            platform="youtube",
            platform_id=channel_id,
            name=name,
            avatar_url=avatar_url,
            description=description,
            home_url=home_url,
        )
    except ValueError:
        raise
    except Exception as e:
        logger.warning("RSS获取频道信息失败: %s，尝试yt-dlp降级", e)
        # RSS失败时降级到yt-dlp
        try:
            from tracker_youtube_ytdlp import get_creator_info as ytdlp_get_creator_info
            creator_info = ytdlp_get_creator_info(url)
            logger.info("yt-dlp降级获取频道信息成功: %s", creator_info.name)
            return creator_info
        except Exception as ytdlp_e:
            logger.error("yt-dlp降级也失败: %s", ytdlp_e)
            raise ValueError(f"获取YouTube频道信息失败: RSS错误={e}; yt-dlp错误={ytdlp_e}")


def get_recent_videos(channel_id: str, hours: int = 72) -> list[VideoItem]:
    """
    获取频道近期视频列表（指定小时数内发布的视频）

    策略：
    1. 先尝试RSS方式（速度快，但只返回最近15个视频）
    2. 如果RSS获取的视频数量不足或 oldest_video 在 cutoff 内，
       说明可能有更多视频被截断，降级到yt-dlp获取（可获取50个）
    """
    import feedparser

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    videos = []

    try:
        rss_url = f"{YOUTUBE_RSS_URL}?channel_id={channel_id}"

        transport_kwargs = {}
        if _PROXY_URL:
            transport_kwargs["proxy"] = _PROXY_URL

        with httpx.Client(timeout=15, follow_redirects=True, **transport_kwargs) as client:
            resp = client.get(rss_url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            })
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)

        for entry in feed.entries:
            # 解析发布时间
            pub_parsed = entry.get("published_parsed")
            if not pub_parsed:
                continue

            # published_parsed 是 time.struct_time，转为 datetime
            try:
                pub_time = datetime(
                    pub_parsed.tm_year, pub_parsed.tm_mon, pub_parsed.tm_mday,
                    pub_parsed.tm_hour, pub_parsed.tm_min, pub_parsed.tm_sec,
                    tzinfo=timezone.utc,
                )
            except Exception:
                continue

            if pub_time < cutoff:
                continue

            # 提取video_id
            entry_id = entry.get("id", "")
            video_id = ""
            if "yt:video:" in entry_id:
                video_id = entry_id.replace("yt:video:", "")
            else:
                # 从link中提取
                link = entry.get("link", "")
                m = re.search(r"v=([a-zA-Z0-9_-]{11})", link)
                if m:
                    video_id = m.group(1)

            if not video_id:
                continue

            # 提取缩略图
            thumbnail = ""
            media_content = entry.get("media_content", [])
            for mc in media_content:
                if mc.get("medium") == "image" or "thumbnail" in mc.get("type", ""):
                    thumbnail = mc.get("url", "")
                    break
            if not thumbnail:
                # YouTube标准缩略图URL
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"

            # 提取描述
            description = entry.get("summary", "")[:200]
            # 清理HTML标签
            description = re.sub(r"<[^>]+>", "", description).strip()

            # 提取播放量（RSS中可能在media:community中）
            view_count = 0
            media_community = entry.get("media_community", {})
            if media_community:
                stats = media_community.get("media_statistics", {})
                view_count = int(stats.get("views", 0))

            title = entry.get("title", "")
            link = entry.get("link", f"https://www.youtube.com/watch?v={video_id}")

            videos.append(VideoItem(
                video_id=video_id,
                title=title,
                url=link,
                published_at=pub_time.isoformat(),
                duration=0,  # RSS不提供时长
                thumbnail=thumbnail,
                view_count=view_count,
                description=description,
            ))

        # === 降级策略：如果RSS返回的视频 oldest 仍在 cutoff 内，说明可能有更多视频 ===
        need_fallback = False
        if videos:
            # 按发布时间排序（RSS默认已按时间倒序）
            oldest_video_time = datetime.fromisoformat(videos[-1].published_at)
            if oldest_video_time >= cutoff:
                # 最旧的视频仍在时间范围内，但被RSS截断了，需要yt-dlp补充
                need_fallback = True
                logger.info(
                    "RSS返回%d个视频，但最旧视频(%s)仍在%d小时cutoff(%s)内，"
                    "降级到yt-dlp获取完整列表",
                    len(videos),
                    oldest_video_time.strftime("%Y-%m-%d %H:%M"),
                    hours,
                    cutoff.strftime("%Y-%m-%d %H:%M"),
                )
        else:
            # RSS没有返回任何视频，可能是RSS问题，尝试yt-dlp
            need_fallback = True
            logger.info("RSS未返回视频，尝试yt-dlp降级方案")

        if need_fallback:
            try:
                from tracker_youtube_ytdlp import get_recent_videos as ytdlp_get_videos
                ytdlp_videos = ytdlp_get_videos(channel_id, hours=hours)
                if ytdlp_videos:
                    logger.info("yt-dlp成功获取%d个视频，替换RSS结果", len(ytdlp_videos))
                    return ytdlp_videos
            except Exception as e:
                logger.warning("yt-dlp降级获取失败: %s，继续使用RSS结果", e)

        return videos

    except Exception as e:
        logger.error("获取YouTube频道视频失败 channel_id=%s: %s", channel_id, e)
        # RSS完全失败时，尝试yt-dlp降级
        try:
            from tracker_youtube_ytdlp import get_recent_videos as ytdlp_get_videos
            ytdlp_videos = ytdlp_get_videos(channel_id, hours=hours)
            logger.info("RSS失败后yt-dlp降级成功，获取%d个视频", len(ytdlp_videos))
            return ytdlp_videos
        except Exception as ytdlp_e:
            logger.error("yt-dlp降级也失败: %s", ytdlp_e)
        return []
