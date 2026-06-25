"""
提醒管理 API + SSE 实时通知推送。
使用 ReminderService 封装业务逻辑。
（第三阶段 F1/F3 重构：DB 操作 async → def，SSE 保持 async）
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.reminders import SetReminderRequest, ReminderResponse, ReminderListResponse
from app.schemas.auth import MessageResponse
from app.services.reminder_service import ReminderService
from app.middleware.auth import require_admin
from app.dependencies import get_reminder_service

router = APIRouter()


@router.get("/api/reminders", response_model=ReminderListResponse)
def get_reminders(
    status: str = None,
    service: ReminderService = Depends(get_reminder_service),
    _: bool = Depends(require_admin),
):
    """获取所有提醒（需 admin 鉴权）"""
    return ReminderListResponse(reminders=service.get_all_reminders(status))


@router.get("/api/reminders/{reminder_id}", response_model=ReminderResponse)
def get_reminder(
    reminder_id: str,
    service: ReminderService = Depends(get_reminder_service),
    _: bool = Depends(require_admin),
):
    """获取单个提醒（需 admin 鉴权）"""
    reminder = service.get_reminder(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return reminder


@router.post("/api/reminders")
def set_reminder(
    request: SetReminderRequest,
    service: ReminderService = Depends(get_reminder_service),
    _: bool = Depends(require_admin),
):
    """设置提醒（需 admin 鉴权）"""
    reminder_id = service.set_reminder(request.message, request.minutes, request.hour, request.minute)
    if reminder_id is None:
        raise HTTPException(status_code=400, detail="请提供 minutes 或 hour+minute")
    return {"success": True, "reminder_id": reminder_id}


@router.delete("/api/reminders/{reminder_id}", response_model=MessageResponse)
def cancel_reminder(
    reminder_id: str,
    service: ReminderService = Depends(get_reminder_service),
    _: bool = Depends(require_admin),
):
    """取消提醒（需 admin 鉴权）"""
    if not service.cancel_reminder(reminder_id):
        raise HTTPException(status_code=404, detail="提醒不存在")
    return MessageResponse(message=f"提醒 {reminder_id} 已取消")


@router.get("/api/notifications")
async def notifications(
    service: ReminderService = Depends(get_reminder_service),
    _: bool = Depends(require_admin),
):
    """SSE 实时通知推送（需 admin 鉴权）

    保持 async：内部 await 订阅迭代器。
    """
    async def event_generator():
        import asyncio
        sub_iter = service.subscribe()

        async def next_or_none():
            """从异步迭代器取下一个值，结束时返回 None 而不抛 StopAsyncIteration"""
            try:
                return await sub_iter.__anext__()
            except StopAsyncIteration:
                return None

        try:
            while True:
                try:
                    message = await asyncio.wait_for(next_or_none(), timeout=30.0)
                    if message is None:
                        break
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            if hasattr(sub_iter, 'aclose'):
                await sub_iter.aclose()
    return StreamingResponse(event_generator(), media_type="text/event-stream")
