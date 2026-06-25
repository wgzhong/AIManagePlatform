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
from .auth import (
    UserCreate, UserPublic, RegisterResponse, TokenResponse,
    RefreshTokenRequest, RefreshTokenResponse, MessageResponse,
)
from .user import (
    UserConfigResponse, UserConfigUpdate, UserConfigUpdateResponse,
    ChatHistoryItem, UserStatsResponse,
)
from .admin import (
    UserListItem, UserListResponse, UserUpdateResponse,
    UserConfigItem, AllUserConfigsResponse,
)

__all__ = [
    "ChatRequest", "ChatResponse",
    "DeviceRegisterRequest", "DeviceResponse", "DeviceListResponse",
    "SetReminderRequest", "ReminderResponse", "ReminderListResponse",
    "SkillConfigUpdate", "SystemPromptRequest",
    "ApiKeyGenerateResponse", "ApiKeyListResponse", "ApiKeyValidateResponse",
    "StatsResponse", "HealthResponse",
    "MoodPromptResponse",
    "UserCreate", "UserPublic", "RegisterResponse", "TokenResponse",
    "RefreshTokenRequest", "RefreshTokenResponse", "MessageResponse",
    "UserConfigResponse", "UserConfigUpdate", "UserConfigUpdateResponse",
    "ChatHistoryItem", "UserStatsResponse",
    "UserListItem", "UserListResponse", "UserUpdateResponse",
    "UserConfigItem", "AllUserConfigsResponse",
]
