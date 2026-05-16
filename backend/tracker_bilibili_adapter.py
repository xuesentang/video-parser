"""B站UP主适配器 - 获取UP主信息和近期视频列表

核心策略（优化后）：
1. 自动生成 buvid3 Cookie（参考 yupi-hot-monitor 方案，无需访问首页）
2. 用 space/acc/info API 获取博主信息（需buvid3 Cookie，无需WBI签名）
3. 用 space/arc/search 获取视频列表（首选，精确按mid过滤）
4. 降级到搜索API（用UP主名搜索，按mid过滤）
5. 两级降级：space/acc/info → card API
"""

import re
import time
import uuid
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, quote

import requests

logger = logging.getLogger("tracker_bilibili")

# 请求头
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

# B站API端点
SPACE_INFO_API = "https://api.bilibili.com/x/space/acc/info"
CARD_INFO_API = "https://api.bilibili.com/x/web-interface/card"
SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
SPACE_SEARCH_API = "https://api.bilibili.com/x/space/arc/search"

# 从URL中提取mid的正则
_MID_PATTERN = re.compile(r"space\.bilibili\.com/(\d+)")

# ============ Session 管理 ============

_session: Optional[requests.Session] = None
_session_created_at: float = 0
_SESSION_TTL = 600  # 10分钟过期

# 全局请求时间戳，用于限流
_last_request_time: float = 0
_MIN_REQUEST_INTERVAL = 1.5  # 最小请求间隔1.5秒（优化后）
_MAX_ADAPTIVE_INTERVAL = 5.0  # 自适应上限5秒（优化后）

# 连续失败计数，用于自适应加长等待
_consecutive_failures: int = 0


def _rate_limit_wait():
    """确保请求间隔不低于阈值，避免触发B站限流

    轻量自适应策略：连续失败越多，等待越长（最高5秒），
    请求成功后恢复正常间隔
    """
    global _last_request_time, _consecutive_failures

    # 轻量自适应间隔：基础1.5秒 + 连续失败惩罚（每次+0.5秒，上限5秒）
    adaptive_interval = min(_MIN_REQUEST_INTERVAL + _consecutive_failures * 0.5, _MAX_ADAPTIVE_INTERVAL)

    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < adaptive_interval:
        wait = adaptive_interval - elapsed
        logger.debug("限流等待 %.1fs (连续失败=%d)", wait, _consecutive_failures)
        time.sleep(wait)
    _last_request_time = time.time()


def mark_request_success():
    """标记请求成功，重置连续失败计数"""
    global _consecutive_failures
    _consecutive_failures = 0


def mark_request_failure():
    """标记请求失败，增加连续失败计数"""
    global _consecutive_failures
    _consecutive_failures += 1


def _init_session() -> requests.Session:
    """初始化Session，自动生成buvid3 Cookie（参考yupi-hot-monitor方案）

    优化：使用uuid随机生成buvid3，无需访问B站首页，节省5-15秒
    """
    global _session, _session_created_at

    now = time.time()
    if _session and (now - _session_created_at) < _SESSION_TTL:
        return _session

    logger.info("初始化B站Session，生成buvid3 Cookie...")
    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)

    # 自动生成buvid3（无需访问首页）
    buvid3 = f"{uuid.uuid4()}infoc"
    sess.cookies.set("buvid3", buvid3, domain=".bilibili.com")
    logger.info("B站Cookie生成成功: buvid3=%s...", buvid3[:20])

    _session = sess
    _session_created_at = now
    return sess


def _get_session() -> requests.Session:
    """获取Session（自动过期刷新）"""
    now = time.time()
    if _session and (now - _session_created_at) < _SESSION_TTL:
        return _session
    return _init_session()


# ============ 数据类 ============

@dataclass
class VideoItem:
    """标准化视频条目"""
    video_id: str
    title: str
    url: str
    published_at: str  # ISO 8601
    duration: int      # 秒
    thumbnail: str
    view_count: int
    description: str


@dataclass
class CreatorInfo:
    """标准化博主信息"""
    platform: str = "bilibili"
    platform_id: str = ""   # mid
    name: str = ""
    avatar_url: str = ""
    description: str = ""
    home_url: str = ""


# ============ 博主信息缓存 ============

_creator_info_cache: dict[str, tuple[CreatorInfo, float]] = {}
_CREATOR_CACHE_TTL = 600  # 10分钟


def get_creator_info_cached(url: str) -> CreatorInfo:
    """带缓存的博主信息获取"""
    mid = extract_mid_from_url(url)
    if not mid:
        mid = url.strip().split("/")[-1].split("?")[0]

    now = time.time()
    if mid in _creator_info_cache:
        info, cached_at = _creator_info_cache[mid]
        if now - cached_at < _CREATOR_CACHE_TTL:
            logger.debug("命中博主信息缓存 mid=%s", mid)
            return info

    info = get_creator_info(url)
    _creator_info_cache[mid] = (info, now)
    return info


# ============ URL 解析 ============

def is_bilibili_space_url(url: str) -> bool:
    """判断是否为B站UP主主页链接"""
    try:
        host = urlparse(url).netloc.lower()
        return "space.bilibili.com" in host
    except Exception:
        return False


def extract_mid_from_url(url: str) -> Optional[str]:
    """从B站UP主主页URL中提取mid"""
    m = _MID_PATTERN.search(url)
    return m.group(1) if m else None


# ============ 核心 API ============

def get_creator_info(url: str) -> CreatorInfo:
    """
    输入UP主主页URL，返回博主信息。
    两级降级策略（优化后移除网页解析）：
    1. space/acc/info API（需buvid3 Cookie，无需WBI签名）
    2. card API（备用，同样需Cookie）
    """
    mid = extract_mid_from_url(url)
    if not mid:
        mid = url.strip().split("/")[-1].split("?")[0]
        if not mid.isdigit():
            raise ValueError("无法从URL中提取B站UP主mid，请输入正确的个人空间链接")

    session = _get_session()

    # === 方案1: space/acc/info ===
    for attempt in range(2):  # 3次→2次
        try:
            _rate_limit_wait()
            resp = session.get(
                SPACE_INFO_API,
                params={"mid": mid},
                timeout=(10, 30),
                headers=DEFAULT_HEADERS,
            )
            data = resp.json()

            if data.get("code") == 0:
                mark_request_success()
                info = data.get("data", {})
                return CreatorInfo(
                    platform="bilibili",
                    platform_id=str(mid),
                    name=info.get("name", "未知UP主"),
                    avatar_url=info.get("face", ""),
                    description=info.get("sign", "")[:200],
                    home_url=f"https://space.bilibili.com/{mid}",
                )

            error_code = data.get("code", -1)
            error_msg = data.get("message", "未知错误")

            if error_code == -799 or "频繁" in error_msg:
                # 限流，等待后重试（缩短等待时间）
                mark_request_failure()
                wait = 4 * (attempt + 1)  # 8秒→4秒
                logger.warning("space/acc/info限流 mid=%s, 等待%ds", mid, wait)
                time.sleep(wait)
                if attempt < 1:
                    _init_session()  # 刷新Session
                    session = _get_session()
                continue

            # 其他错误，跳到备用方案
            logger.warning("space/acc/info错误 code=%s msg=%s", error_code, error_msg)
            break

        except requests.RequestException as e:
            logger.warning("space/acc/info请求异常: %s", e)
            if attempt < 1:
                time.sleep(2 * (2 ** attempt))

    # === 方案2: card API ===
    try:
        _rate_limit_wait()
        resp = session.get(
            CARD_INFO_API,
            params={"mid": mid, "photo": "true"},
            timeout=(10, 30),
            headers=DEFAULT_HEADERS,
        )
        data = resp.json()

        if data.get("code") == 0:
            mark_request_success()
            card = data.get("data", {}).get("card", {})
            return CreatorInfo(
                platform="bilibili",
                platform_id=str(mid),
                name=card.get("name", "未知UP主"),
                avatar_url=card.get("face", ""),
                description=card.get("sign", "")[:200],
                home_url=f"https://space.bilibili.com/{mid}",
            )
        logger.warning("card API失败: code=%s msg=%s", data.get("code"), data.get("message"))
    except Exception as e:
        logger.warning("card API异常: %s", e)

    raise ValueError("获取B站UP主信息失败（2种方案均失败），请稍后重试")


def get_recent_videos(mid: str, hours: int = 24, creator_name: str = "") -> list[VideoItem]:
    """
    获取UP主近期视频列表。

    策略：
    1. 先尝试 space/arc/search API（需要WBI签名，可能被限流）
    2. 降级到搜索API（用UP主名搜索，按mid过滤）

    注意：creator_name 用于搜索API降级方案，建议传入
    """
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    session = _get_session()
    videos = []

    # === 方案1: space/arc/search（如果可用） ===
    try:
        videos = _fetch_videos_via_space_api(mid, cutoff, session)
        if videos:
            return videos
    except Exception as e:
        logger.warning("space API获取视频失败: %s", e)

    # === 方案2: 搜索API（用UP主名搜索，按mid过滤） ===
    if not creator_name:
        # 尝试从space/acc/info获取名字
        try:
            _rate_limit_wait()
            resp = session.get(
                SPACE_INFO_API,
                params={"mid": mid},
                timeout=(10, 30),
                headers=DEFAULT_HEADERS,
            )
            data = resp.json()
            if data.get("code") == 0:
                creator_name = data["data"].get("name", "")
        except Exception:
            pass

    if creator_name:
        try:
            videos = _fetch_videos_via_search_api(mid, creator_name, cutoff, session)
        except Exception as e:
            logger.warning("搜索API获取视频失败: %s", e)

    return videos


def _fetch_videos_via_space_api(mid: str, cutoff, session: requests.Session) -> list[VideoItem]:
    """通过space/arc/search API获取视频（可能被限流）"""
    from datetime import datetime, timezone

    videos = []
    page = 1
    page_size = 30

    while page <= 3:
        _rate_limit_wait()
        try:
            resp = session.get(
                SPACE_SEARCH_API,
                params={
                    "mid": mid,
                    "ps": page_size,
                    "tid": 0,
                    "pn": page,
                    "order": "pubdate",
                },
                timeout=(10, 30),
                headers={**DEFAULT_HEADERS, "Referer": f"https://space.bilibili.com/{mid}/video"},
            )
            data = resp.json()

            error_code = data.get("code", 0)
            if error_code == -799 or error_code == -412 or error_code == -352:
                mark_request_failure()
                logger.warning("space API限流/封禁 code=%s，切换到搜索API", error_code)
                return videos  # 不再重试，直接返回已获取的

            if error_code != 0:
                mark_request_failure()
                logger.warning("space API错误 code=%s msg=%s", error_code, data.get("message"))
                return videos

            mark_request_success()

        except Exception as e:
            logger.warning("space API请求异常: %s", e)
            return videos

        vlist = data.get("data", {}).get("list", {}).get("vlist", [])
        if not vlist:
            break

        for v in vlist:
            created_ts = v.get("created", 0)
            if created_ts <= 0:
                continue
            pub_time = datetime.fromtimestamp(created_ts, tz=timezone.utc)
            if pub_time < cutoff:
                return videos

            video_id = v.get("bvid", "")
            pic = v.get("pic", "")
            if pic and pic.startswith("//"):
                pic = "https:" + pic
            length_str = v.get("length", "0:00")

            videos.append(VideoItem(
                video_id=video_id,
                title=v.get("title", ""),
                url=f"https://www.bilibili.com/video/{video_id}",
                published_at=pub_time.isoformat(),
                duration=_parse_duration(length_str),
                thumbnail=pic,
                view_count=v.get("play", 0) or 0,
                description=(v.get("description", "") or "")[:200],
            ))

        time.sleep(2.5)
        page += 1

    return videos


def _fetch_videos_via_search_api(
    mid: str, creator_name: str, cutoff, session: requests.Session
) -> list[VideoItem]:
    """通过搜索API获取UP主的视频列表"""
    from datetime import datetime, timezone

    videos = []
    page = 1

    while page <= 2:  # 搜索API最多2页
        _rate_limit_wait()
        try:
            resp = session.get(
                SEARCH_API,
                params={
                    "search_type": "video",
                    "keyword": creator_name,
                    "page": page,
                    "page_size": 20,
                    "order": "pubdate",
                },
                timeout=(10, 30),
                headers=DEFAULT_HEADERS,
            )
            data = resp.json()

            if data.get("code") != 0:
                mark_request_failure()
                logger.warning("搜索API错误: code=%s msg=%s", data.get("code"), data.get("message"))
                break

            mark_request_success()

        except Exception as e:
            logger.warning("搜索API请求异常: %s", e)
            break

        results = data.get("data", {}).get("result", [])
        if not results:
            break

        # 只保留该UP主的视频
        for r in results:
            if str(r.get("mid")) != str(mid):
                continue

            # 解析发布时间
            pubdate_ts = r.get("pubdate", 0)
            if pubdate_ts <= 0:
                continue
            pub_time = datetime.fromtimestamp(pubdate_ts, tz=timezone.utc)
            if pub_time < cutoff:
                continue

            video_id = r.get("bvid", "")
            pic = r.get("pic", "")
            if pic and pic.startswith("//"):
                pic = "https:" + pic

            # 搜索API的duration格式是 "12:34" 或秒数
            duration_val = r.get("duration", 0)
            if isinstance(duration_val, int) and duration_val > 0:
                duration = duration_val
            elif isinstance(duration_val, str):
                duration = _parse_duration(duration_val)
            else:
                duration = 0

            # 清理标题中的HTML标签
            title = re.sub(r"<[^>]+>", "", r.get("title", ""))

            videos.append(VideoItem(
                video_id=video_id,
                title=title,
                url=f"https://www.bilibili.com/video/{video_id}",
                published_at=pub_time.isoformat(),
                duration=duration,
                thumbnail=pic,
                view_count=r.get("play", 0) or 0,
                description=(r.get("description", "") or "")[:200],
            ))

        # 搜索结果可能不多，检查是否还有下一页
        num_results = data.get("data", {}).get("numResults", 0)
        if num_results <= page * 20:
            break

        time.sleep(2)
        page += 1

    return videos


def _parse_duration(length_str: str) -> int:
    """将时长字符串(如 '12:34' 或 '1:23:45')转为秒数"""
    try:
        parts = str(length_str).split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 0
    except (ValueError, IndexError):
        return 0
