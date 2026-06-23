"""
API Key 管理相关的请求/响应模型
"""

from typing import List
from pydantic import BaseModel


class ApiKeyGenerateResponse(BaseModel):
    """生成 API Key 响应模型"""
    key: str
    message: str


class ApiKeyListResponse(BaseModel):
    """API Key 列表响应模型"""
    keys: List[str]


class ApiKeyValidateResponse(BaseModel):
    """验证 API Key 响应模型"""
    valid: bool
