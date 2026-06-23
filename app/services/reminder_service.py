"""
提醒服务模块
封装提醒管理业务逻辑
"""

from typing import Optional, List

from app.core.reminder_manager import reminder_manager
from app.schemas.reminders import ReminderResponse


class ReminderService:
    """提醒服务类"""
    
    def get_all_reminders(self, status: Optional[str] = None) -> List[ReminderResponse]:
        """获取所有提醒"""
        reminders = reminder_manager.get_all_reminders(status)
        return [self._to_response(r) for r in reminders]
    
    def get_reminder(self, reminder_id: str) -> Optional[ReminderResponse]:
        """获取单个提醒"""
        reminder = reminder_manager.get_reminder(reminder_id)
        if not reminder:
            return None
        return self._to_response(reminder)
    
    def set_reminder(self, message: str, minutes: Optional[int] = None,
                     hour: Optional[int] = None, minute: Optional[int] = None) -> Optional[str]:
        """设置提醒"""
        if minutes is not None:
            return reminder_manager.set_reminder_in_minutes(message, minutes)
        elif hour is not None and minute is not None:
            return reminder_manager.set_reminder_at_time(message, hour, minute)
        return None
    
    def cancel_reminder(self, reminder_id: str) -> bool:
        """取消提醒"""
        return reminder_manager.cancel_reminder(reminder_id)
    
    async def subscribe(self):
        """订阅 SSE 通知"""
        async for message in reminder_manager.subscribe():
            yield message
    
    def _to_response(self, reminder: dict) -> ReminderResponse:
        """转换为响应模型"""
        return ReminderResponse(
            id=reminder.get("id", ""),
            message=reminder.get("message", ""),
            trigger_time=reminder.get("trigger_time", ""),
            repeat_type=reminder.get("repeat_type", "once"),
            repeat_interval=reminder.get("repeat_interval", 0),
            repeat_count=reminder.get("repeat_count", 0),
            status=reminder.get("status", "pending"),
            created_at=reminder.get("created_at", ""),
            triggered_count=reminder.get("triggered_count", 0),
        )
