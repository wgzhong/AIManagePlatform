"""
管理员用户管理响应模型（第三阶段 F3）。
"""

from typing import List
from pydantic import BaseModel, EmailStr


class UserListItem(BaseModel):
    """用户列表项"""
    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: str = ""


class UserListResponse(BaseModel):
    """用户列表响应"""
    users: List[UserListItem]


class UserUpdateResponse(BaseModel):
    """用户更新响应"""
    message: str
    user: UserListItem


class UserConfigItem(BaseModel):
    """单个用户配置（管理员视图，API Key 脱敏）"""
    user_id: int
    username: str
    email: str
    is_superuser: bool
    api_key: str = ""
    api_url: str = ""
    default_model: str = ""
    mood: str = ""
    custom_models: list = []


class AllUserConfigsResponse(BaseModel):
    """所有用户配置响应"""
    configs: List[UserConfigItem]
