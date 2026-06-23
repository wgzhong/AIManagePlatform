"""
设备管理相关的请求/响应模型
"""

from typing import Optional
from pydantic import BaseModel


class DeviceRegisterRequest(BaseModel):
    """设备注册请求模型"""
    device_name: str = "Hardware Device"
    admin_api_key: Optional[str] = None


class DeviceResponse(BaseModel):
    """设备信息响应模型"""
    device_code: str
    name: str
    admin_api_key_short: str
    created_at: str
    last_used: Optional[str]
    usage_count: int


class DeviceListResponse(BaseModel):
    """设备列表响应模型"""
    devices: list[DeviceResponse]
    total: int
    api_keys_total: int
