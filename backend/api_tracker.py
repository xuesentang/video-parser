"""博主追踪系统 - API路由
博主CRUD、报告查看、手动触发报告生成
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel

from auth import get_current_user
from tracker_database import (
    get_or_create_creator,
    add_subscription,
    get_user_subscriptions,
    get_subscription_by_id,
    update_subscription,
    delete_subscription,
    get_user_reports,
    get_report_by_id,
    delete_report,
)
from tracker_bilibili_adapter import (
    get_creator_info as bilibili_get_creator_info,
    is_bilibili_space_url,
)
from tracker_youtube_adapter import (
    get_creator_info as youtube_get_creator_info,
    is_youtube_channel_url,
)
from tracker_scheduler import generate_report_for_user

logger = logging.getLogger("api_tracker")

router = APIRouter(prefix="/api/tracker", tags=["tracker"])


# ============================================================
# Request/Response Models
# ============================================================

class AddCreatorRequest(BaseModel):
    url: str


class UpdateSubscriptionRequest(BaseModel):
    alias: Optional[str] = None
    group_tag: Optional[str] = None


class GenerateReportRequest(BaseModel):
    time_range_hours: int = 72


# ============================================================
# 博主/订阅管理
# ============================================================

@router.post("/creators")
async def add_creator(req: AddCreatorRequest, user: dict = Depends(get_current_user)):
    """添加博主订阅（输入主页URL，自动识别平台）"""
    url = req.url.strip()
    user_id = user["id"]

    try:
        if is_bilibili_space_url(url):
            creator_info = await asyncio.get_event_loop().run_in_executor(
                None, bilibili_get_creator_info, url
            )
        elif is_youtube_channel_url(url):
            # 先尝试RSS方式（原有逻辑）
            try:
                creator_info = await asyncio.get_event_loop().run_in_executor(
                    None, youtube_get_creator_info, url
                )
            except Exception:
                # RSS失败时自动降级到yt-dlp
                from tracker_youtube_ytdlp import get_creator_info as ytdlp_get_creator_info
                creator_info = await asyncio.get_event_loop().run_in_executor(
                    None, ytdlp_get_creator_info, url
                )
        else:
            raise HTTPException(status_code=400, detail="不支持的平台或URL格式。请输入B站UP主空间链接或YouTube频道链接")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取博主信息失败: {str(e)}")

    creator = get_or_create_creator(
        platform=creator_info.platform,
        platform_id=creator_info.platform_id,
        name=creator_info.name,
        avatar_url=creator_info.avatar_url,
        description=creator_info.description,
        home_url=creator_info.home_url,
    )

    try:
        subscription = add_subscription(user_id, creator["id"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "success": True,
        "data": {
            "sub_id": subscription["id"],
            "creator_id": creator["id"],
            "platform": creator_info.platform,
            "platform_id": creator_info.platform_id,
            "name": creator_info.name,
            "avatar_url": creator_info.avatar_url,
            "description": creator_info.description,
            "home_url": creator_info.home_url,
        },
    }


@router.get("/creators")
async def list_creators(user: dict = Depends(get_current_user)):
    """获取当前用户的订阅博主列表"""
    subscriptions = get_user_subscriptions(user["id"])

    grouped = {"bilibili": [], "youtube": []}
    for sub in subscriptions:
        platform = sub["platform"]
        if platform not in grouped:
            grouped[platform] = []
        grouped[platform].append({
            "sub_id": sub["sub_id"],
            "creator_id": sub["creator_id"],
            "platform": platform,
            "platform_id": sub["platform_id"],
            "name": sub["name"],
            "avatar_url": sub["avatar_url"],
            "description": sub["description"],
            "home_url": sub["home_url"],
            "status": sub["status"],
            "alias": sub["alias"],
            "group_tag": sub["group_tag"],
            "last_checked_at": sub["last_checked_at"],
        })

    return {"success": True, "data": grouped}


@router.patch("/creators/{sub_id}")
async def update_creator_subscription(
    sub_id: int,
    req: UpdateSubscriptionRequest,
    user: dict = Depends(get_current_user),
):
    """更新订阅的别名/分组"""
    existing = get_subscription_by_id(sub_id, user["id"])
    if not existing:
        raise HTTPException(status_code=404, detail="订阅不存在")

    update_subscription(sub_id, user["id"], alias=req.alias, group_tag=req.group_tag)
    return {"success": True, "message": "更新成功"}


@router.delete("/creators/{sub_id}")
async def remove_creator(sub_id: int, user: dict = Depends(get_current_user)):
    """删除订阅"""
    success = delete_subscription(sub_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return {"success": True, "message": "已取消订阅"}


# ============================================================
# 报告管理
# ============================================================

@router.get("/reports")
async def list_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """获取报告列表"""
    reports = get_user_reports(user["id"], limit=limit, offset=offset)
    return {"success": True, "data": reports}


@router.get("/reports/{report_id}")
async def get_report(report_id: int, user: dict = Depends(get_current_user)):
    """获取报告详情"""
    report = get_report_by_id(report_id, user["id"])
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if report["status"] == "no_videos":
        return {
            "success": True,
            "data": {
                **report,
                "display_message": "过去72小时内您追踪的博主都没有发布新视频，无需生成报告。",
            },
        }
    if report["status"] == "no_subscription":
        return {
            "success": True,
            "data": {
                **report,
                "display_message": "您还没有订阅任何博主，请先添加博主后再生成报告。",
            },
        }

    return {"success": True, "data": report}


@router.delete("/reports/{report_id}")
async def delete_report_api(report_id: int, user: dict = Depends(get_current_user)):
    """删除报告"""
    success = delete_report(report_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"success": True, "message": "报告已删除"}


@router.post("/reports/generate")
async def trigger_report(
    background_tasks: BackgroundTasks,
    req: GenerateReportRequest,
    user: dict = Depends(get_current_user),
):
    """手动触发报告生成（后台异步执行，通过轮询获取进度）"""
    from tracker_database import create_report
    from datetime import datetime, timezone, timedelta

    today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    report = create_report(user["id"], today_str)
    report_id = report["id"]

    background_tasks.add_task(generate_report_for_user, user["id"], report_id)

    return {
        "success": True,
        "message": "报告生成已启动",
        "data": {"report_id": report_id},
    }


@router.get("/reports/{report_id}/progress")
async def get_report_progress(report_id: int, user: dict = Depends(get_current_user)):
    """查询报告生成进度（前端轮询此接口）"""
    report = get_report_by_id(report_id, user["id"])
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return {
        "success": True,
        "data": {
            "report_id": report_id,
            "status": report["status"],
            "progress_current": report.get("progress_current", 0),
            "progress_total": report.get("progress_total", 0),
            "current_creator": report.get("current_creator", ""),
            "video_count": report.get("video_count", 0),
        },
    }
