"""AI 视频总结相关 API 路由（独立模块，通过 include_router 挂载）"""

import asyncio
import json
from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from auth import get_current_user
from database import check_and_increment_summary, NORMAL_USER_USAGE_LIMIT

router = APIRouter(prefix="/api", tags=["AI 总结"])


class SummarizeRequest(BaseModel):
    url: str
    language: str = "zh"


class ChatRequest(BaseModel):
    url: str
    question: str
    subtitle_text: str = ""


def _check_summary_permission(user: dict):
    """
    检查 AI 总结权限。
    VIP 用户：无限制。
    普通用户：使用统一额度（20次）。
    返回 (allowed, remaining, message)
    """
    allowed, remaining = check_and_increment_summary(user["id"])
    if not allowed:
        return False, 0, f"使用额度已用完（共{NORMAL_USER_USAGE_LIMIT}次），升级VIP可无限使用"

    return True, remaining, None


def _get_summarizer():
    """延迟初始化 VideoSummarizer（仅在首次调用时创建）"""
    from summarizer import VideoSummarizer
    if not hasattr(_get_summarizer, "_instance"):
        try:
            _get_summarizer._instance = VideoSummarizer()
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
    return _get_summarizer._instance


def _get_extractor():
    """延迟初始化 SubtitleExtractor"""
    from summarizer import SubtitleExtractor
    if not hasattr(_get_extractor, "_instance"):
        _get_extractor._instance = SubtitleExtractor()
    return _get_extractor._instance


@router.post("/summarize", response_class=EventSourceResponse)
async def summarize_video(req: SummarizeRequest, user: dict = Depends(get_current_user)) -> AsyncIterable[ServerSentEvent]:
    """
    AI 视频总结（SSE 流式）
    事件类型: subtitle / summary / mindmap / done / error / quota
    """
    allowed, remaining, message = _check_summary_permission(user)
    if not allowed:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": message, "need_vip": True}, ensure_ascii=False),
            event="error",
        )
        return

    try:
        loop = asyncio.get_event_loop()
        extractor = _get_extractor()
        subtitle_data = await loop.run_in_executor(
            None, extractor.extract, req.url
        )

        yield ServerSentEvent(
            raw_data=json.dumps(subtitle_data, ensure_ascii=False),
            event="subtitle",
        )

        if not subtitle_data["has_subtitle"]:
            # 无字幕时，推送一个提示性的 summary 事件后正常结束
            # 这样前端可以展示"该视频无字幕"的提示，而不是报错弹窗
            yield ServerSentEvent(
                raw_data=json.dumps("该视频没有可用的字幕，无法生成总结。请尝试其他带有字幕的视频。", ensure_ascii=False),
                event="summary",
            )
            yield ServerSentEvent(
                raw_data=json.dumps({"markdown": "## 无字幕\n\n该视频没有可用的字幕，无法生成思维导图。"}, ensure_ascii=False),
                event="mindmap",
            )
            quota_info = {"remaining": remaining, "limit": NORMAL_USER_USAGE_LIMIT}
            yield ServerSentEvent(
                raw_data=json.dumps(quota_info, ensure_ascii=False),
                event="quota",
            )
            yield ServerSentEvent(raw_data="[DONE]", event="done")
            return

        full_text = subtitle_data["full_text"]
        subtitle_type = subtitle_data.get("subtitle_type", "")
        summarizer = _get_summarizer()

        for token in summarizer.summarize_stream(full_text, req.language, subtitle_type):
            yield ServerSentEvent(raw_data=json.dumps(token, ensure_ascii=False), event="summary")

        mindmap_md = await loop.run_in_executor(
            None, summarizer.generate_mindmap, full_text, req.language, subtitle_type
        )
        yield ServerSentEvent(
            raw_data=json.dumps({"markdown": mindmap_md}, ensure_ascii=False),
            event="mindmap",
        )

        quota_info = {"remaining": remaining, "limit": NORMAL_USER_USAGE_LIMIT}
        yield ServerSentEvent(
            raw_data=json.dumps(quota_info, ensure_ascii=False),
            event="quota",
        )

        yield ServerSentEvent(raw_data="[DONE]", event="done")

    except Exception as e:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": f"总结失败: {str(e)}"}, ensure_ascii=False),
            event="error",
        )


@router.post("/chat", response_class=EventSourceResponse)
async def chat_with_video(req: ChatRequest, user: dict = Depends(get_current_user)) -> AsyncIterable[ServerSentEvent]:
    """AI 视频问答（SSE 流式）"""
    try:
        if not req.subtitle_text.strip():
            loop = asyncio.get_event_loop()
            extractor = _get_extractor()
            subtitle_data = await loop.run_in_executor(
                None, extractor.extract, req.url
            )
            if not subtitle_data["has_subtitle"]:
                yield ServerSentEvent(
                    raw_data=json.dumps("该视频没有可用的字幕，无法回答问题。请尝试其他带有字幕的视频。", ensure_ascii=False),
                    event="answer",
                )
                yield ServerSentEvent(raw_data="[DONE]", event="done")
                return
            subtitle_text = subtitle_data["full_text"]
        else:
            subtitle_text = req.subtitle_text

        summarizer = _get_summarizer()
        for token in summarizer.chat_stream(subtitle_text, req.question):
            yield ServerSentEvent(raw_data=json.dumps(token, ensure_ascii=False), event="answer")

        yield ServerSentEvent(raw_data="[DONE]", event="done")

    except Exception as e:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": f"回答失败: {str(e)}"}, ensure_ascii=False),
            event="error",
        )
