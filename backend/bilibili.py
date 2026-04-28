"""
B站视频解析与下载模块
基于 B站公开 API，无需 Cookie 和登录
原理：提取 BV 号 → view API 获取元数据 → playurl API 获取视频流地址
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests

logger = logging.getLogger("bilibili")

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

_BVID_PATTERN = re.compile(r"(BV[a-zA-Z0-9]+)")
_AVID_PATTERN = re.compile(r"av(\d+)", re.IGNORECASE)


def is_bilibili_url(url: str) -> bool:
    """判断是否为 B站链接"""
    bilibili_domains = [
        "bilibili.com", "www.bilibili.com", "m.bilibili.com",
        "b23.tv", "www.b23.tv",
    ]
    try:
        host = urlparse(url).netloc.lower()
        return any(d in host for d in bilibili_domains)
    except Exception:
        return False


class BilibiliParser:
    """B站视频解析器，无需 Cookie，基于公开 API"""

    VIEW_API = "https://api.bilibili.com/x/web-interface/view"
    PLAYURL_API = "https://api.bilibili.com/x/player/playurl"

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = (10, 30)
        self.max_retries = 3

    def parse(self, url: str) -> dict:
        """解析 B站视频信息，返回统一格式"""
        resolved_url = self._resolve_short_url(url)
        bvid = self._extract_bvid(resolved_url)
        avid = None
        if not bvid:
            avid = self._extract_avid(resolved_url)
            if not avid:
                raise ValueError("无法从链接中提取 BV 号或 AV 号")

        view_data = self._fetch_view_info(bvid=bvid, avid=avid)
        return self._build_result(view_data)

    def _resolve_short_url(self, url: str) -> str:
        """解析 b23.tv 短链接重定向"""
        parsed = urlparse(url)
        if "b23.tv" not in (parsed.netloc or ""):
            return url

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    url, timeout=self.timeout,
                    allow_redirects=True, headers=DEFAULT_HEADERS,
                )
                resp.raise_for_status()
                return resp.url
            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    logger.warning("短链接解析失败: %s, 使用原始链接", e)
                    return url
                time.sleep(1 * (2 ** attempt))
        return url

    @staticmethod
    def _extract_bvid(url: str) -> Optional[str]:
        """从 URL 中提取 BV 号"""
        # 先从路径中匹配
        m = _BVID_PATTERN.search(url)
        return m.group(1) if m else None

    @staticmethod
    def _extract_avid(url: str) -> Optional[int]:
        """从 URL 中提取 AV 号"""
        m = _AVID_PATTERN.search(url)
        return int(m.group(1)) if m else None

    def _fetch_view_info(self, bvid: str = None, avid: int = None) -> dict:
        """通过 B站 view API 获取视频信息"""
        params = {}
        if bvid:
            params["bvid"] = bvid
        elif avid:
            params["aid"] = avid
        else:
            raise ValueError("需要提供 bvid 或 avid")

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    self.VIEW_API, params=params,
                    timeout=self.timeout, headers=DEFAULT_HEADERS,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 0:
                    raise ValueError(f"B站 API 错误: {data.get('message', '未知错误')}")
                return data.get("data", {})
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise ValueError(f"获取视频信息失败: {e}")
                time.sleep(1 * (2 ** attempt))
        raise ValueError("获取视频信息失败")

    def _fetch_play_url(self, avid: int, cid: int, qn: int = 64) -> dict:
        """通过 B站 playurl API 获取视频流地址"""
        params = {
            "avid": avid,
            "cid": cid,
            "qn": qn,
            "fourk": 1,
            "fnval": 16,  # 请求 DASH 格式
        }
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    self.PLAYURL_API, params=params,
                    timeout=self.timeout, headers=DEFAULT_HEADERS,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 0:
                    raise ValueError(f"B站 playurl API 错误: {data.get('message', '未知错误')}")
                return data.get("data", {})
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise ValueError(f"获取视频流地址失败: {e}")
                time.sleep(1 * (2 ** attempt))
        raise ValueError("获取视频流地址失败")

    def _build_result(self, view_data: dict) -> dict:
        """构建与 yt-dlp 解析结果兼容的统一格式"""
        bvid = view_data.get("bvid", "")
        avid = view_data.get("aid", 0)
        cid = view_data.get("cid", 0)
        title = view_data.get("title", "未知标题")
        desc = view_data.get("desc", "")
        duration = view_data.get("duration", 0)
        owner = view_data.get("owner", {})
        stat = view_data.get("stat", {})

        # 尝试获取视频流信息
        formats = []
        try:
            play_data = self._fetch_play_url(avid, cid)
            formats = self._extract_formats(play_data)
        except Exception as e:
            logger.warning("获取视频流地址失败，将使用 yt-dlp 兜底下载: %s", e)
            # 提供一个标记，告诉 main.py 使用 yt-dlp 下载
            formats = [{
                "format_id": "bestvideo+bestaudio/best",
                "ext": "mp4",
                "resolution": "最佳",
                "height": 1080,
                "filesize": None,
                "filesize_approx": None,
                "vcodec": "h264",
                "acodec": "aac",
                "has_audio": True,
                "label": "最佳 MP4 (视频+音频)",
                "_use_ytdlp": True,
            }]

        # 缩略图
        pic = view_data.get("pic", "")
        # 发布日期
        pubdate = view_data.get("pubdate", 0)
        upload_date = ""
        if pubdate:
            upload_date = time.strftime("%Y%m%d", time.localtime(pubdate))

        # 分P信息
        pages = view_data.get("pages", [])
        subtitles_available = []
        if pages:
            for page in pages[:5]:
                subtitles_available.append(page.get("part", ""))

        return {
            "id": bvid,
            "title": title,
            "thumbnail": pic,
            "duration": duration,
            "duration_string": self._fmt_duration(duration),
            "uploader": owner.get("name", "B站用户"),
            "platform": "BiliBili",
            "view_count": stat.get("view", 0),
            "upload_date": upload_date,
            "description": (desc or "")[:200],
            "formats": formats,
            "subtitles": [],
            "automatic_captions": [],
        }

    def _extract_formats(self, play_data: dict) -> list:
        """从 playurl API 返回数据中提取格式列表"""
        formats = []
        accept_quality = play_data.get("accept_quality", [])
        accept_description = play_data.get("accept_description", [])

        dash = play_data.get("dash", {})
        video_streams = dash.get("video", [])
        audio_streams = dash.get("audio", [])

        # DASH 格式：构建视频+音频组合
        if video_streams:
            # 取最高质量视频流
            best_video = video_streams[0]
            best_audio = audio_streams[0] if audio_streams else None

            v_height = best_video.get("height", 1080)
            v_width = best_video.get("width", 1920)
            v_codecs = best_video.get("codecs", "avc1")

            if best_audio:
                a_codecs = best_audio.get("codecs", "mp4a")
                label = f"{v_height}p DASH MP4 (视频+音频)"
                formats.append({
                    "format_id": f"dash-{v_height}p",
                    "ext": "mp4",
                    "resolution": f"{v_width}x{v_height}",
                    "height": v_height,
                    "filesize": None,
                    "filesize_approx": None,
                    "vcodec": v_codecs,
                    "acodec": a_codecs,
                    "has_audio": True,
                    "label": label,
                    "_video_url": best_video.get("baseUrl") or best_video.get("base_url", ""),
                    "_audio_url": best_audio.get("baseUrl") or best_audio.get("base_url", ""),
                })

            # 纯视频流
            for i, vs in enumerate(video_streams[:8]):
                h = vs.get("height", 0)
                w = vs.get("width", 0)
                codecs = vs.get("codecs", "avc1")
                formats.append({
                    "format_id": f"dash-video-{h}p",
                    "ext": "mp4",
                    "resolution": f"{w}x{h}",
                    "height": h,
                    "filesize": None,
                    "filesize_approx": None,
                    "vcodec": codecs,
                    "acodec": None,
                    "has_audio": False,
                    "label": f"{h}p DASH (仅视频)",
                    "_video_url": vs.get("baseUrl") or vs.get("base_url", ""),
                })

            # 纯音频流
            for i, as_ in enumerate(audio_streams[:3]):
                codecs = as_.get("codecs", "mp4a")
                formats.append({
                    "format_id": f"dash-audio-{i}",
                    "ext": "mp4",
                    "resolution": "音频",
                    "height": 0,
                    "filesize": None,
                    "filesize_approx": None,
                    "vcodec": "none",
                    "acodec": codecs,
                    "has_audio": True,
                    "label": f"音频 {codecs}",
                    "_audio_url": as_.get("baseUrl") or as_.get("base_url", ""),
                })

        # 非 DASH 格式（低质量但有直链）
        durl = play_data.get("durl", [])
        if durl:
            for i, d in enumerate(durl[:3]):
                url = d.get("url", "")
                quality = play_data.get("quality", 32)
                height_map = {32: 360, 64: 480, 80: 720, 112: 1080, 116: 1080, 120: 4320}
                h = height_map.get(quality, 480)
                formats.append({
                    "format_id": f"durl-{quality}",
                    "ext": "mp4",
                    "resolution": f"{'?'}x{h}",
                    "height": h,
                    "filesize": d.get("size"),
                    "filesize_approx": None,
                    "vcodec": "h264",
                    "acodec": "aac",
                    "has_audio": True,
                    "label": f"{h}p MP4 直链",
                    "_direct_url": url,
                })

        formats.sort(key=lambda x: x.get("height", 0), reverse=True)
        return formats[:15]

    @staticmethod
    def _fmt_duration(seconds: Optional[int]) -> str:
        if not seconds:
            return "00:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
