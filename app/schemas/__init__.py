"""
Schemas 模块入口
统一导出所有请求/响应模型
"""

from .chat import ChatRequest, ChatResponse
from .devices import DeviceRegisterRequest, DeviceResponse, DeviceListResponse
from .reminders import SetReminderRequest, ReminderResponse, ReminderListResponse
from .skills import SkillConfigUpdate, SystemPromptRequest
from .keys import ApiKeyGenerateResponse, ApiKeyListResponse, ApiKeyValidateResponse
from .stats import StatsResponse, HealthResponse
from .mood import MoodPromptResponse

__all__ = [
    "ChatRequest", "ChatResponse",
    "DeviceRegisterRequest", "DeviceResponse", "DeviceListResponse",
    "SetReminderRequest", "ReminderResponse", "ReminderListResponse",
    "SkillConfigUpdate", "SystemPromptRequest",
    "ApiKeyGenerateResponse", "ApiKeyListResponse", "ApiKeyValidateResponse",
    "StatsResponse", "HealthResponse",
    "MoodPromptResponse",
]
