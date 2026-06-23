"""
提醒管理相关的请求/响应模型
"""

from typing import Optional
from pydantic import BaseModel


class SetReminderRequest(BaseModel):
    """设置提醒请求模型"""
    message: str
    minutes: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None


class ReminderResponse(BaseModel):
    """提醒信息响应模型"""
    id: str
    message: str
    trigger_time: str
    repeat_type: str
    repeat_interval: int
    repeat_count: int
    status: str
    created_at: str
    triggered_count: int


class ReminderListResponse(BaseModel):
    """提醒列表响应模型"""
    reminders: list[ReminderResponse]
