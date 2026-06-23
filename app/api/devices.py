"""
设备管理 API（ESP32 设备码）。
使用 DeviceService 封装业务逻辑。
"""

from fastapi import APIRouter, Depends, Form, HTTPException

from app.schemas.devices import DeviceResponse, DeviceListResponse
from app.services.device_service import DeviceService
from app.middleware.auth import require_admin

router = APIRouter()


def get_device_service() -> DeviceService:
    return DeviceService()


@router.post("/api/devices/register")
async def register_device(
    device_name: str = Form(default="Hardware Device"),
    admin_api_key: str = Form(default=None),
    service: DeviceService = Depends(get_device_service),
):
    """注册新设备，使用用户提供的 API Key"""
    return service.register_device(device_name, admin_api_key)


@router.get("/api/devices", response_model=DeviceListResponse)
async def list_devices(service: DeviceService = Depends(get_device_service)):
    """列出所有已注册的设备"""
    return service.list_devices()


@router.delete("/api/devices/{device_code}")
async def delete_device(device_code: str, service: DeviceService = Depends(get_device_service), _: bool = Depends(require_admin)):
    """删除指定设备（需 admin 鉴权）"""
    result = service.delete_device(device_code)
    if result is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return result


@router.get("/api/devices/{device_code}", response_model=DeviceResponse)
async def get_device(device_code: str, service: DeviceService = Depends(get_device_service)):
    """获取指定设备信息"""
    device = service.get_device(device_code)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device
