import base64
import os
import tempfile
import logging

logger = logging.getLogger("config")

PROXY_URL = os.getenv("PROXY_URL", "")

_COOKIES_FILE_PATH = None


def get_cookies_file_path() -> str | None:
    global _COOKIES_FILE_PATH

    if _COOKIES_FILE_PATH is not None:
        if os.path.exists(_COOKIES_FILE_PATH):
            return _COOKIES_FILE_PATH
        _COOKIES_FILE_PATH = None

    direct_path = os.getenv("YOUTUBE_COOKIES_FILE", "")
    if direct_path and os.path.isfile(direct_path):
        _COOKIES_FILE_PATH = direct_path
        logger.info("YouTube Cookie 文件: YOUTUBE_COOKIES_FILE=%s", direct_path)
        return _COOKIES_FILE_PATH

    b64_data = os.getenv("YOUTUBE_COOKIES_B64", "")
    if b64_data:
        try:
            cookies_content = base64.b64decode(b64_data)
            tmp = tempfile.NamedTemporaryFile(
                mode="wb", suffix=".txt", prefix="yt_cookies_",
                delete=False,
            )
            tmp.write(cookies_content)
            tmp.close()
            _COOKIES_FILE_PATH = tmp.name
            logger.info("YouTube Cookie 文件: 从 YOUTUBE_COOKIES_B64 解码写入 %s", tmp.name)
            return _COOKIES_FILE_PATH
        except Exception as e:
            logger.error("解码 YOUTUBE_COOKIES_B64 失败: %s", e)

    default_path = os.path.join(os.path.dirname(__file__), "cookies.txt")
    if os.path.isfile(default_path):
        _COOKIES_FILE_PATH = default_path
        logger.info("YouTube Cookie 文件: backend/cookies.txt")
        return _COOKIES_FILE_PATH

    return None


def get_ydl_cookie_option() -> dict:
    cookies_path = get_cookies_file_path()
    if cookies_path:
        return {"cookiefile": cookies_path}
    return {}


def get_ydl_runtime_options() -> dict:
    return {
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }
