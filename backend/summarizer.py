import json
import os
import re
import tempfile
import time
from typing import Optional

import httpx
import yt_dlp
from openai import OpenAI

from config import PROXY_URL, get_ydl_cookie_option, get_ydl_runtime_options


def _is_bilibili_url(url: str) -> bool:
    return "bilibili.com" in url or "b23.tv" in url


def _is_douyin_url(url: str) -> bool:
    douyin_domains = ["douyin.com", "iesdouyin.com", "v.douyin.com",
                      "www.douyin.com", "m.douyin.com"]
    return any(d in url for d in douyin_domains)


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_PROXY_URL = PROXY_URL


def _safe_request(
    url: str,
    headers: Optional[dict] = None,
    timeout: float = 15.0,
    max_retries: int = 3,
    base_delay: float = 1.0,
    is_json: bool = True,
    proxy: Optional[str] = None,
) -> Optional[httpx.Response]:
    """
    带重试和指数退避的安全 HTTP 请求。

    参数:
        url: 请求地址
        headers: 自定义请求头（不传则使用默认浏览器请求头）
        timeout: 单次请求超时时间（秒）
        max_retries: 最大重试次数（不含首次）
        base_delay: 基础退避延迟（秒），实际延迟 = base_delay * (2 ** retry_count)
        is_json: 是否期望返回 JSON（用于解析错误时降级）
        proxy: 代理地址（如 http://127.0.0.1:7890）

    返回:
        httpx.Response 对象，或 None（全部重试后仍失败）

    策略说明:
        - 遇到 429 (Too Many Requests) 时额外增加 5 秒等待
        - 每次请求间隔至少 1 秒，避免触发限流
        - 仅对可重试错误（网络错误、429、5xx）进行重试，4xx（除429外）不重试
    """
    request_headers = dict(_BROWSER_HEADERS)
    if headers:
        request_headers.update(headers)

    # 代理优先级: 参数 > 环境变量
    effective_proxy = proxy or _PROXY_URL or None

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            transport_kwargs = {}
            if effective_proxy:
                transport_kwargs["proxy"] = effective_proxy
            with httpx.Client(timeout=timeout, follow_redirects=True, **transport_kwargs) as client:
                resp = client.get(url, headers=request_headers)
            if resp.status_code == 429:
                # 429 特殊处理：额外等待
                wait_time = base_delay * (2 ** attempt) + 5.0
                time.sleep(wait_time)
                last_exception = Exception(f"HTTP 429 on attempt {attempt + 1}")
                continue
            if resp.status_code >= 500:
                # 服务器错误，可以重试
                wait_time = base_delay * (2 ** attempt)
                time.sleep(wait_time)
                last_exception = Exception(f"HTTP {resp.status_code} on attempt {attempt + 1}")
                continue
            if resp.status_code >= 400:
                # 4xx 客户端错误（除429外），不重试
                return None
            return resp
        except (httpx.NetworkError, httpx.TimeoutException, httpx.ConnectError) as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = base_delay * (2 ** attempt)
                time.sleep(wait_time)
            continue
        except Exception as e:
            # 其他未知异常，不重试
            last_exception = e
            break

    return None


def _parse_json3_subtitle(data: dict) -> list[dict]:
    """
    解析 YouTube json3 格式字幕为统一分段结构。

    json3 是 YouTube 的默认字幕格式，包含最完整的时序信息。
    结构: {"events": [{"tStartMs": 0, "dDurationMs": 5000, "segs": [{"utf8": "文本"}]}]}
    """
    segments = []
    events = data.get("events", [])
    for event in events:
        start_ms = event.get("tStartMs", 0)
        duration_ms = event.get("dDurationMs", 0)
        end_ms = start_ms + duration_ms
        segs = event.get("segs", [])
        text_parts = []
        for seg in segs:
            utf8_text = seg.get("utf8", "")
            if utf8_text and utf8_text != "\n":
                text_parts.append(utf8_text)
        if text_parts:
            text = "".join(text_parts).strip()
            if text:
                segments.append({
                    "start": round(start_ms / 1000.0, 2),
                    "end": round(end_ms / 1000.0, 2),
                    "text": text,
                })
    return segments


def _parse_srv3_subtitle(data: dict) -> list[dict]:
    """
    解析 YouTube srv3 格式字幕。

    srv3 结构: {"body": {"p": [{"$": {"t": "0", "d": "5000"}, "_": "文本"}]}}
    """
    segments = []
    body = data.get("body", {})
    paragraphs = body.get("p", [])
    for p in paragraphs:
        if isinstance(p, dict):
            attrs = p.get("$", {})
            start_ms = int(attrs.get("t", 0))
            duration_ms = int(attrs.get("d", 0))
            end_ms = start_ms + duration_ms
            text = p.get("_", "").strip()
        elif isinstance(p, str):
            continue
        else:
            continue
        if text:
            segments.append({
                "start": round(start_ms / 1000.0, 2),
                "end": round(end_ms / 1000.0, 2),
                "text": text,
            })
    return segments


def _parse_ttml_subtitle(content: str) -> list[dict]:
    """
    解析 TTML 格式字幕。

    TTML 是 XML 格式，包含 <p begin="00:00:00.000" end="00:00:05.000">文本</p>
    """
    segments = []
    # 匹配 <p begin="..." end="...">文本</p>
    pattern = re.compile(
        r'<p[^>]*begin="([^"]*)"[^>]*end="([^"]*)"[^>]*>(.*?)</p>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(content):
        begin_str = match.group(1).strip()
        end_str = match.group(2).strip()
        text = re.sub(r"<[^>]+>", "", match.group(3)).strip()
        if text:
            try:
                start = _time_str_to_seconds(begin_str)
                end = _time_str_to_seconds(end_str)
                segments.append({
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "text": text,
                })
            except Exception:
                continue
    return segments


def _time_str_to_seconds(time_str: str) -> float:
    """将时间字符串转为秒数，支持多种格式。"""
    time_str = time_str.strip()
    # 尝试匹配 HH:MM:SS.mmm 或 MM:SS.mmm
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
    # 尝试纯毫秒数
    try:
        return float(time_str) / 1000.0
    except ValueError:
        pass
    raise ValueError(f"无法解析时间格式: {time_str}")


class SubtitleExtractor:
    """从视频 URL 提取平台字幕（人工字幕 > 自动字幕）"""

    PREFERRED_LANGS = ["zh-Hans", "zh", "zh-CN", "en", "ja", "ko"]
    SUBTITLE_FORMAT = "json3"

    # 类级别时间戳，用于控制请求间隔
    _last_request_time = 0.0
    _min_request_interval = 1.0  # 两次请求之间至少间隔 1 秒

    def _rate_limited_request(self, url: str, headers: Optional[dict] = None) -> Optional[httpx.Response]:
        """带请求间隔控制的 safe_request 包装。"""
        now = time.time()
        elapsed = now - SubtitleExtractor._last_request_time
        if elapsed < SubtitleExtractor._min_request_interval:
            time.sleep(SubtitleExtractor._min_request_interval - elapsed)
        SubtitleExtractor._last_request_time = time.time()
        return _safe_request(url, headers=headers)

    def extract(self, url: str) -> dict:
        """
        提取视频字幕，返回:
        {
            "has_subtitle": bool,
            "language": str,
            "subtitle_type": "manual" | "auto" | "desc" | "none",
            "segments": [{"start": float, "end": float, "text": str}, ...],
            "full_text": str
        }
        """
        # 抖音专用路径：提取字幕，无字幕时用视频描述降级
        if _is_douyin_url(url):
            result = self._extract_douyin(url)
            if result["has_subtitle"]:
                return result
            # 无字幕降级：用视频描述生成伪字幕
            return self._extract_douyin_desc_as_subtitle(url)

        # B站专用路径
        if _is_bilibili_url(url):
            result = self._extract_bilibili(url)
            if result["has_subtitle"]:
                return result

        # 兜底：yt-dlp 通用方案
        info = self._get_video_info(url)

        manual_subs = info.get("subtitles") or {}
        auto_subs = info.get("automatic_captions") or {}

        manual_subs = {k: v for k, v in manual_subs.items() if k != "danmaku"}

        lang, sub_url, sub_type, fmt_ext = self._pick_best_subtitle(manual_subs, auto_subs)
        if not sub_url:
            return {
                "has_subtitle": False,
                "language": "",
                "subtitle_type": "none",
                "segments": [],
                "full_text": "",
            }

        segments = self._download_and_parse_subtitle(sub_url, fmt_ext)

        if not segments:
            # 如果首选语言下载失败，尝试其他可用语言降级
            segments, lang, sub_type = self._try_fallback_subtitles(manual_subs, auto_subs, lang)

        if not segments:
            return {
                "has_subtitle": False,
                "language": "",
                "subtitle_type": "none",
                "segments": [],
                "full_text": "",
            }

        full_text = " ".join(seg["text"] for seg in segments)

        return {
            "has_subtitle": True,
            "language": lang,
            "subtitle_type": sub_type,
            "segments": segments,
            "full_text": full_text,
        }

    def _try_fallback_subtitles(
        self, manual_subs: dict, auto_subs: dict, excluded_lang: str
    ) -> tuple[list[dict], str, str]:
        """
        当首选语言字幕下载失败时，尝试其他可用语言。

        降级顺序：
        1. PREFERRED_LANGS 中除 excluded_lang 外的其他语言
        2. manual_subs 中第一个可用语言
        3. auto_subs 中第一个可用语言
        """
        all_langs = [l for l in self.PREFERRED_LANGS if l != excluded_lang]
        for lang in all_langs:
            if lang in manual_subs:
                url, fmt_ext = self._get_format_url_with_ext(manual_subs[lang])
                if url:
                    segments = self._download_and_parse_subtitle(url, fmt_ext)
                    if segments:
                        return segments, lang, "manual"
            if lang in auto_subs:
                url, fmt_ext = self._get_format_url_with_ext(auto_subs[lang])
                if url:
                    segments = self._download_and_parse_subtitle(url, fmt_ext)
                    if segments:
                        return segments, lang, "auto"

        # 尝试 manual_subs 中第一个可用语言
        for lang, formats in manual_subs.items():
            if lang == excluded_lang:
                continue
            url, fmt_ext = self._get_format_url_with_ext(formats)
            if url:
                segments = self._download_and_parse_subtitle(url, fmt_ext)
                if segments:
                    return segments, lang, "manual"

        # 尝试 auto_subs 中第一个可用语言
        for lang, formats in auto_subs.items():
            if lang == excluded_lang:
                continue
            url, fmt_ext = self._get_format_url_with_ext(formats)
            if url:
                segments = self._download_and_parse_subtitle(url, fmt_ext)
                if segments:
                    return segments, lang, "auto"

        return [], "", "none"

    def _extract_douyin(self, url: str) -> dict:
        """抖音专用字幕提取，绕开 yt-dlp 的 Cookie 依赖"""
        empty = {
            "has_subtitle": False, "language": "", "subtitle_type": "none",
            "segments": [], "full_text": "",
        }
        try:
            from douyin import DouyinParser
            parser = DouyinParser()
            share_url = parser._extract_url(url)
            resolved_url = parser._resolve_redirect(share_url)
            video_id = parser._extract_video_id(resolved_url)

            # 尝试通过抖音 API 获取字幕信息
            item_info = parser._fetch_item_info(video_id, resolved_url)
            subtitle_info = (item_info.get("video", {})
                             .get("subtitle", {}))
            subtitle_list = subtitle_info.get("subtitleInfos", [])

            if not subtitle_list:
                return empty

            # 尝试获取中文字幕
            target_sub = None
            for sub in subtitle_list:
                lang = sub.get("LanguageCodeName", "")
                if lang in ("zh", "zh-Hans", "zh-CN"):
                    target_sub = sub
                    break
            if not target_sub:
                target_sub = subtitle_list[0]

            sub_url = target_sub.get("Url", "")
            if not sub_url:
                return empty
            if sub_url.startswith("//"):
                sub_url = "https:" + sub_url

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.douyin.com/",
            }
            sub_resp = self._rate_limited_request(sub_url, headers=headers)
            if not sub_resp:
                return empty

            sub_json = sub_resp.json()

            body = sub_json.get("body", [])
            if not body:
                return empty

            segments = []
            for item in body:
                content = item.get("content", "").strip()
                if not content:
                    continue
                segments.append({
                    "start": round(item.get("start", 0), 2),
                    "end": round(item.get("end", 0), 2),
                    "text": content,
                })

            if not segments:
                return empty

            full_text = " ".join(seg["text"] for seg in segments)
            return {
                "has_subtitle": True,
                "language": target_sub.get("LanguageCodeName", "zh"),
                "subtitle_type": "auto",
                "segments": segments,
                "full_text": full_text,
            }
        except Exception:
            return empty

    def _extract_douyin_desc_as_subtitle(self, url: str) -> dict:
        """抖音无字幕时，用视频描述 + 标签作为伪字幕降级"""
        empty = {
            "has_subtitle": False, "language": "", "subtitle_type": "none",
            "segments": [], "full_text": "",
        }
        try:
            from douyin import DouyinParser
            parser = DouyinParser()
            share_url = parser._extract_url(url)
            resolved_url = parser._resolve_redirect(share_url)
            video_id = parser._extract_video_id(resolved_url)
            item_info = parser._fetch_item_info(video_id, resolved_url)

            desc = (item_info.get("desc") or "").strip()
            if not desc:
                return empty

            # 提取话题标签作为补充信息
            text_extra = item_info.get("text_extra", [])
            hashtags = []
            for extra in text_extra:
                tag = extra.get("hashtagName", "")
                if tag:
                    hashtags.append(f"#{tag}")

            full_text = desc
            if hashtags:
                full_text += "\n话题标签: " + " ".join(hashtags)

            # 用描述生成单段伪字幕
            return {
                "has_subtitle": True,
                "language": "zh",
                "subtitle_type": "desc",
                "segments": [{"start": 0.0, "end": 0.0, "text": full_text}],
                "full_text": full_text,
            }
        except Exception:
            return empty

    def _extract_bilibili(self, url: str) -> dict:
        """B 站专用字幕提取（通过 dm/view API 获取 CC 字幕和 AI 字幕）"""
        empty = {
            "has_subtitle": False, "language": "", "subtitle_type": "none",
            "segments": [], "full_text": "",
        }
        try:
            bvid = self._parse_bvid(url)
            if not bvid:
                return empty

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": f"https://www.bilibili.com/video/{bvid}",
            }

            view_resp = self._rate_limited_request(
                f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
                headers=headers,
            )
            if not view_resp:
                return empty

            view_data = view_resp.json().get("data", {})
            cid = view_data.get("cid")
            aid = view_data.get("aid")
            if not cid or not aid:
                return empty

            dm_resp = self._rate_limited_request(
                f"https://api.bilibili.com/x/v2/dm/view?aid={aid}&oid={cid}&type=1",
                headers=headers,
            )
            if not dm_resp:
                return empty

            dm_data = dm_resp.json().get("data", {})
            subtitle_list = dm_data.get("subtitle", {}).get("subtitles", [])

            if not subtitle_list:
                return empty

            best = subtitle_list[0]
            for s in subtitle_list:
                lang = s.get("lan", "")
                if lang == "zh" or lang == "zh-Hans":
                    best = s
                    break

            sub_type = "auto" if best.get("lan", "").startswith("ai-") else "manual"

            sub_url = best.get("subtitle_url", "")
            if sub_url.startswith("//"):
                sub_url = "https:" + sub_url
            if sub_url.startswith("http://"):
                sub_url = "https://" + sub_url[7:]

            if not sub_url:
                return empty

            sub_resp = self._rate_limited_request(sub_url, headers=headers)
            if not sub_resp:
                return empty

            sub_json = sub_resp.json()
            body = sub_json.get("body", [])

            segments = []
            for item in body:
                content = item.get("content", "").strip()
                if not content:
                    continue
                segments.append({
                    "start": round(item.get("from", 0), 2),
                    "end": round(item.get("to", 0), 2),
                    "text": content,
                })

            full_text = " ".join(seg["text"] for seg in segments)
            return {
                "has_subtitle": True,
                "language": best.get("lan", "zh"),
                "subtitle_type": sub_type,
                "segments": segments,
                "full_text": full_text,
            }
        except Exception:
            return empty

    @staticmethod
    def _parse_bvid(url: str) -> Optional[str]:
        m = re.search(r"(BV[a-zA-Z0-9]+)", url)
        return m.group(1) if m else None

    def _get_video_info(self, url: str) -> dict:
        ydl_opts = {
            **get_ydl_runtime_options(),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extract_flat": False,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "skip_download": True,
            "http_headers": dict(_BROWSER_HEADERS),
        }
        if _PROXY_URL:
            ydl_opts["proxy"] = _PROXY_URL
        ydl_opts.update(get_ydl_cookie_option())
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("无法解析该视频链接")
        return info

    def _pick_best_subtitle(
        self, manual_subs: dict, auto_subs: dict
    ) -> tuple[str, Optional[str], str, str]:
        """按优先级选择最佳字幕，返回 (lang, url, type, format_ext)"""
        for lang in self.PREFERRED_LANGS:
            if lang in manual_subs:
                formats = manual_subs[lang]
                url, ext = self._get_format_url_with_ext(formats)
                if url:
                    return lang, url, "manual", ext

        for lang in self.PREFERRED_LANGS:
            if lang in auto_subs:
                formats = auto_subs[lang]
                url, ext = self._get_format_url_with_ext(formats)
                if url:
                    return lang, url, "auto", ext

        if manual_subs:
            first_lang = next(iter(manual_subs))
            url, ext = self._get_format_url_with_ext(manual_subs[first_lang])
            if url:
                return first_lang, url, "manual", ext

        if auto_subs:
            first_lang = next(iter(auto_subs))
            url, ext = self._get_format_url_with_ext(auto_subs[first_lang])
            if url:
                return first_lang, url, "auto", ext

        return "", None, "none", ""

    @staticmethod
    def _get_format_url_with_ext(formats: list) -> tuple[Optional[str], str]:
        """
        获取最佳格式 URL 和格式扩展名。
        优先级: json3 > srv3 > vtt > ttml
        返回: (url, ext)
        """
        preferred = ["json3", "srv3", "vtt", "ttml"]
        for pref in preferred:
            for fmt in formats:
                if fmt.get("ext") == pref:
                    return fmt.get("url"), pref
        if formats:
            return formats[0].get("url"), formats[0].get("ext", "")
        return None, ""

    def _download_and_parse_subtitle(self, sub_url: str, fmt_ext: str) -> list[dict]:
        """
        直接下载字幕 URL 并解析，保留原始格式。

        参数:
            sub_url: 字幕文件的直链 URL
            fmt_ext: 字幕格式扩展名（json3, srv3, vtt, ttml 等）

        返回:
            字幕分段列表
        """
        resp = self._rate_limited_request(sub_url)
        if not resp:
            return []

        try:
            if fmt_ext == "json3":
                data = resp.json()
                return _parse_json3_subtitle(data)
            elif fmt_ext == "srv3":
                data = resp.json()
                return _parse_srv3_subtitle(data)
            elif fmt_ext == "ttml":
                return _parse_ttml_subtitle(resp.text)
            elif fmt_ext == "vtt":
                return self._parse_vtt_text(resp.text)
            else:
                # 未知格式，先尝试 JSON，再尝试 VTT/TTML
                try:
                    data = resp.json()
                    if "events" in data:
                        return _parse_json3_subtitle(data)
                    if "body" in data and "p" in data.get("body", {}):
                        return _parse_srv3_subtitle(data)
                    return []
                except Exception:
                    text = resp.text
                    if "<?xml" in text or "<tt" in text:
                        return _parse_ttml_subtitle(text)
                    return self._parse_vtt_text(text)
        except Exception:
            return []

    @staticmethod
    def _parse_vtt_text(content: str) -> list[dict]:
        """解析 VTT 字幕文本为结构化分段"""
        segments = []
        blocks = re.split(r"\n\n+", content)
        time_pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})"
        )

        seen_texts = set()
        for block in blocks:
            lines = block.strip().split("\n")
            time_match = None
            text_lines = []
            for line in lines:
                m = time_pattern.search(line)
                if m:
                    time_match = m
                elif time_match and line.strip() and not line.strip().isdigit():
                    clean = re.sub(r"<[^>]+>", "", line.strip())
                    if clean:
                        text_lines.append(clean)

            if time_match and text_lines:
                text = " ".join(text_lines)
                if text in seen_texts:
                    continue
                seen_texts.add(text)

                start = _time_to_seconds(time_match.group(1))
                end = _time_to_seconds(time_match.group(2))
                segments.append({
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "text": text,
                })

        return segments


class VideoSummarizer:
    """使用 DeepSeek API 生成视频总结、思维导图、问答"""

    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 环境变量未设置")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = "deepseek-chat"

    def summarize_stream(self, subtitle_text: str, language: str = "zh", subtitle_type: str = ""):
        """流式生成视频总结，yield 每个 token"""
        prompt = self._build_summary_prompt(subtitle_text, language, subtitle_type)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个专业的视频内容分析助手，擅长提取关键信息并生成结构化的总结。"},
                {"role": "user", "content": prompt},
            ],
            stream=True,
            temperature=0.7,
            max_tokens=4096,
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def generate_mindmap(self, subtitle_text: str, language: str = "zh", subtitle_type: str = "") -> str:
        """生成思维导图 Markdown（非流式，一次性返回）"""
        prompt = self._build_mindmap_prompt(subtitle_text, language, subtitle_type)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个专业的思维导图生成助手，擅长将内容组织为清晰的层级结构。"},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            temperature=0.5,
            max_tokens=4096,
        )
        return response.choices[0].message.content

    def chat_stream(self, subtitle_text: str, question: str):
        """基于视频内容的 AI 问答，流式返回"""
        prompt = self._build_chat_prompt(subtitle_text, question)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个视频内容问答助手。根据提供的视频字幕内容来回答用户的问题。如果问题超出视频内容范围，请诚实告知。"},
                {"role": "user", "content": prompt},
            ],
            stream=True,
            temperature=0.7,
            max_tokens=2048,
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    @staticmethod
    def _build_summary_prompt(subtitle_text: str, language: str, subtitle_type: str = "") -> str:
        truncated = subtitle_text[:15000]
        lang_hint = "中文" if language.startswith("zh") else "与原文相同的语言"
        if subtitle_type == "desc":
            return f"""请根据以下抖音视频的描述信息进行分析，使用{lang_hint}输出。

注意：该视频没有字幕，以下内容来自视频的描述和标签，请基于这些信息进行分析。

要求输出格式：
## 视频概述
（根据描述概括视频的主题和内容）

## 内容分析
（根据视频描述和标签推断视频可能涉及的内容要点）

## 关键信息
（提取描述中的重要信息，用编号列表形式）

## 总结
（用1-2句话给出整体评价或一句话总结）

---
视频描述内容：
{truncated}"""
        return f"""请对以下视频字幕内容进行深度总结分析，使用{lang_hint}输出。

要求输出格式：
## 视频概述
（用2-3句话概括视频的主题和核心内容）

## 内容大纲
（按视频内容的逻辑顺序，列出主要章节/段落，每个章节包含要点）

## 核心知识要点
（提取视频中最重要的知识点、观点或结论，用编号列表形式）

## 总结
（用1-2句话给出整体评价或一句话总结）

---
视频字幕内容：
{truncated}"""

    @staticmethod
    def _build_mindmap_prompt(subtitle_text: str, language: str, subtitle_type: str = "") -> str:
        truncated = subtitle_text[:15000]
        lang_hint = "中文" if language.startswith("zh") else "与原文相同的语言"
        desc_note = "\n注意：该视频没有字幕，以下内容来自视频描述，请基于描述信息生成思维导图。" if subtitle_type == "desc" else ""
        return f"""请将以下视频内容整理为思维导图结构，使用{lang_hint}输出。{desc_note}

要求：
1. 使用 Markdown 标题层级格式（# 一级标题，## 二级标题，### 三级标题）
2. 最外层是视频主题
3. 第二层是主要章节/模块
4. 第三层是各章节的要点
5. 可以有第四层做更细的展开
6. 每个节点的文字要简洁精炼
7. 只输出 Markdown 内容，不要其他说明文字

---
视频内容：
{truncated}"""

    @staticmethod
    def _build_chat_prompt(subtitle_text: str, question: str) -> str:
        truncated = subtitle_text[:12000]
        return f"""以下是一个视频的字幕内容，请根据这些内容回答用户的问题。

视频字幕内容：
{truncated}

---
用户问题：{question}

请基于视频内容给出准确、详细的回答。如果视频内容中没有相关信息，请诚实说明。"""


def _time_to_seconds(time_str: str) -> float:
    """将 HH:MM:SS.mmm 转为秒数"""
    parts = time_str.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds
