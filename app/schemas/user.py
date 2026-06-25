"""
用户配置与历史相关的响应模型（第三阶段 F3）。
"""

from typing import Optional, List, Any
from pydantic import BaseModel


class UserConfigResponse(BaseModel):
    """用户配置响应（API Key 脱敏）"""
    api_key: str = ""
    api_url: str = ""
    default_model: str = ""
    mood: str = ""
    custom_models: List[Any] = []
    settings: dict = {}
    skills: List[Any] = []


class UserConfigUpdate(BaseModel):
    """用户配置更新请求体"""
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    default_model: Optional[str] = None
    mood: Optional[str] = None
    custom_models: Optional[list] = None
    settings: Optional[dict] = None
    skills: Optional[list] = None


class UserConfigUpdateResponse(BaseModel):
    """用户配置更新响应"""
    message: str
    config: UserConfigResponse


class ChatHistoryItem(BaseModel):
    """单条聊天记录"""
    role: str
    content: str
    model: Optional[str] = None
    created_at: str


class UserStatsResponse(BaseModel):
    """用户统计数据响应"""
    daily_requests: int = 0
    total_requests: int = 0
    today_input_tokens: int = 0
    today_output_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tool_calls: dict = {}
    daily_records: list = []
    online_devices: int = 0
    total_devices: int = 0
