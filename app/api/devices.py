"""
设备管理 API（ESP32 设备码）。
使用 DeviceService 封装业务逻辑，依赖注入统一走 app/dependencies.py。
（第三阶段 F1/F3 重构：async → def）
"""

from fastapi import APIRouter, Depends, Form, HTTPException

from app.schemas.devices import DeviceResponse, DeviceListResponse
from app.schemas.auth import MessageResponse
from app.services.device_service import DeviceService
from app.middleware.auth import require_admin
from app.dependencies import get_device_service

router = APIRouter()


@router.post("/api/devices/register")
def register_device(
    device_name: str = Form(default="Hardware Device"),
    admin_api_key: str = Form(default=None),
    service: DeviceService = Depends(get_device_service),
    _: bool = Depends(require_admin),
):
    """注册新设备，使用用户提供的 API Key（需 admin 鉴权）"""
    return service.register_device(device_name, admin_api_key)


@router.get("/api/devices", response_model=DeviceListResponse)
def list_devices(
    service: DeviceService = Depends(get_device_service),
    _: bool = Depends(require_admin),
):
    """列出所有已注册的设备（需 admin 鉴权）"""
    return service.list_devices()


@router.delete("/api/devices/{device_code}", response_model=MessageResponse)
def delete_device(
    device_code: str,
    service: DeviceService = Depends(get_device_service),
    _: bool = Depends(require_admin),
):
    """删除指定设备（需 admin 鉴权）"""
    result = service.delete_device(device_code)
    if result is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return MessageResponse(message="设备已删除")


@router.get("/api/devices/{device_code}", response_model=DeviceResponse)
def get_device(
    device_code: str,
    service: DeviceService = Depends(get_device_service),
    _: bool = Depends(require_admin),
):
    """获取指定设备信息（需 admin 鉴权）"""
    device = service.get_device(device_code)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device
