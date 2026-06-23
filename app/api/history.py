"""
对话历史 API。
"""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.chat_history import chat_history_manager
from app.middleware.auth import require_admin

router = APIRouter()


@router.get("/api/chat/history")
async def get_chat_history():
    """获取对话历史"""
    history = chat_history_manager.load_history()
    return {"history": history}


class ChatHistoryRequest(BaseModel):
    """对话历史保存请求"""
    history: List[dict]


@router.post("/api/chat/history")
async def save_chat_history(request: ChatHistoryRequest, _: bool = Depends(require_admin)):
    """保存对话历史（需 admin 鉴权）"""
    chat_history_manager.save_history(request.history)
    return {"success": True}


@router.delete("/api/chat/history")
async def clear_chat_history(_: bool = Depends(require_admin)):
    """清空对话历史（需 admin 鉴权）"""
    chat_history_manager.save_history([])
    return {"success": True}
