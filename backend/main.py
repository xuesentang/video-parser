import os
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import unquote

from dotenv import load_dotenv
load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from downloader import VideoDownloader
from douyin import DouyinParser, is_douyin_url
from bilibili import BilibiliParser, is_bilibili_url
from database import init_db, check_and_increment_usage, NORMAL_USER_USAGE_LIMIT
from auth import get_current_user


downloader = VideoDownloader()
douyin_parser = DouyinParser(download_dir=downloader.DOWNLOAD_DIR)
bilibili_parser = BilibiliParser(download_dir=downloader.DOWNLOAD_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_tracker_tables()
    init_tracker_settings_table()
    yield
    download_dir = downloader.DOWNLOAD_DIR
    if os.path.exists(download_dir):
        for f in os.listdir(download_dir):
            try:
                os.remove(os.path.join(download_dir, f))
            except OSError:
                pass


app = FastAPI(
    title="万能视频下载器 API",
    description="基于 yt-dlp 的万能视频下载服务，支持 1800+ 平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str = "bestvideo+bestaudio/best"


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "万能视频下载器服务运行中"}


@app.post("/api/parse")
async def parse_video(req: ParseRequest, user: dict = Depends(get_current_user)):
    """解析视频信息（抖音走专用模块，其他走 yt-dlp）- 需要登录"""
    # 检查使用额度
    allowed, remaining = check_and_increment_usage(user["id"])
    if not allowed:
        raise HTTPException(status_code=403, detail={
            "success": False,
            "error": f"使用额度已用完（共{NORMAL_USER_USAGE_LIMIT}次），升级VIP可无限使用",
            "need_vip": True
        })

    try:
        loop = asyncio.get_event_loop()
        if is_douyin_url(req.url):
            result = await loop.run_in_executor(None, douyin_parser.parse, req.url)
        elif is_bilibili_url(req.url):
            result = await loop.run_in_executor(None, bilibili_parser.parse, req.url)
        else:
            result = await loop.run_in_executor(None, downloader.parse_video, req.url)
        return {"success": True, "data": result, "remaining": remaining}
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": f"解析失败: {str(e)}"
        })


@app.post("/api/download")
async def download_video(req: DownloadRequest, user: dict = Depends(get_current_user)):
    """服务端下载视频后提供文件下载（抖音/B站走专用模块，其他走 yt-dlp）- 需要登录"""
    # 注意：解析时已扣减额度，下载不再扣减
    try:
        loop = asyncio.get_event_loop()
        if is_douyin_url(req.url):
            result = await loop.run_in_executor(None, douyin_parser.download, req.url)
        elif is_bilibili_url(req.url):
            # B站下载：走 yt-dlp（已添加浏览器请求头，可正常工作）
            result = await loop.run_in_executor(
                None, downloader.download_video, req.url, req.format_id
            )
        else:
            result = await loop.run_in_executor(
                None, downloader.download_video, req.url, req.format_id
            )
        filepath = result["filepath"]
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="下载的文件不存在")

        return FileResponse(
            path=filepath,
            filename=result["filename"],
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": f"下载失败: {str(e)}"
        })


@app.post("/api/direct-url")
async def get_direct_url(req: DownloadRequest, user: dict = Depends(get_current_user)):
    """获取视频直链 - 需要登录"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, downloader.get_direct_url, req.url, req.format_id
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": f"获取直链失败: {str(e)}"
        })


@app.get("/api/proxy/thumbnail")
async def proxy_thumbnail(url: str = Query(..., description="缩略图URL")):
    """代理获取视频缩略图，绕过防盗链"""
    try:
        proxy_url = os.getenv("PROXY_URL", "") or None
        transport_kwargs = {}
        if proxy_url:
            transport_kwargs["proxy"] = proxy_url
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, **transport_kwargs) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": url,
            })
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            return StreamingResponse(
                iter([resp.content]),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception:
        raise HTTPException(status_code=502, detail="缩略图加载失败")


# 挂载功能模块路由
from api_summarize import router as summarize_router
from api_auth import router as auth_router
from api_payment import router as payment_router
from api_tracker import router as tracker_router
from api_batch import router as batch_router
from tracker_database import init_tracker_tables, init_tracker_settings_table

app.include_router(summarize_router)
app.include_router(auth_router)
app.include_router(payment_router)
app.include_router(tracker_router)
app.include_router(batch_router)

# 挂载前端静态文件（生产环境）
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
