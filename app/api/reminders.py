"""
提醒管理 API + SSE 实时通知推送。
使用 ReminderService 封装业务逻辑。
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.reminders import SetReminderRequest, ReminderResponse
from app.services.reminder_service import ReminderService
from app.middleware.auth import require_admin

router = APIRouter()


def get_reminder_service() -> ReminderService:
    return ReminderService()


@router.get("/api/reminders")
async def get_reminders(status: str = None, service: ReminderService = Depends(get_reminder_service)):
    """获取所有提醒"""
    return {"reminders": service.get_all_reminders(status)}


@router.get("/api/reminders/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(reminder_id: str, service: ReminderService = Depends(get_reminder_service)):
    """获取单个提醒"""
    reminder = service.get_reminder(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return reminder


@router.post("/api/reminders")
async def set_reminder(request: SetReminderRequest, service: ReminderService = Depends(get_reminder_service)):
    """设置提醒"""
    reminder_id = service.set_reminder(request.message, request.minutes, request.hour, request.minute)
    if reminder_id is None:
        raise HTTPException(status_code=400, detail="请提供 minutes 或 hour+minute")
    return {"success": True, "reminder_id": reminder_id}


@router.delete("/api/reminders/{reminder_id}")
async def cancel_reminder(reminder_id: str, service: ReminderService = Depends(get_reminder_service), _: bool = Depends(require_admin)):
    """取消提醒（需 admin 鉴权）"""
    if not service.cancel_reminder(reminder_id):
        raise HTTPException(status_code=404, detail="提醒不存在")
    return {"success": True, "message": f"提醒 {reminder_id} 已取消"}


@router.get("/api/notifications")
async def notifications(service: ReminderService = Depends(get_reminder_service)):
    """SSE 实时通知推送"""
    async def event_generator():
        async for message in service.subscribe():
            yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
