"""
认证相关响应模型（第三阶段 F2/F3）。

涵盖：注册、登录、当前用户、登出、刷新令牌。
"""

from typing import Optional
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """用户注册请求模型"""
    username: str
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """对外公开的用户信息（不含密码）"""
    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool = False
    created_at: str = ""


class RegisterResponse(BaseModel):
    """注册响应"""
    id: int
    username: str
    email: str
    is_active: bool
    created_at: str = ""


class TokenResponse(BaseModel):
    """登录响应（含 access_token + refresh_token）"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求体"""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """刷新令牌响应"""
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
