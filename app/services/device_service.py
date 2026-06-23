"""
设备服务模块
封装设备管理业务逻辑
"""

from typing import Dict, Optional

from app.core.devices import device_manager
from app.core.api_keys import api_key_manager
from app.schemas.devices import DeviceResponse, DeviceListResponse


class DeviceService:
    """设备服务类"""
    
    def register_device(self, device_name: str, admin_api_key: str) -> dict:
        """注册新设备"""
        if not admin_api_key or len(admin_api_key) < 10:
            return {
                "success": False,
                "error": "请提供有效的 API Key",
                "message": "请在首页输入您的 API Key 后再注册设备",
            }
        
        result = device_manager.register_device(device_name, admin_api_key)
        device_code = result["device_code"]
        
        return {
            "success": True,
            "device_code": device_code,
            "device_name": device_name,
            "message": f"设备注册成功！设备码：{device_code}",
        }
    
    def get_device(self, device_code: str) -> Optional[DeviceResponse]:
        """获取设备信息"""
        info = device_manager.get_device(device_code)
        if info is None:
            return None
        
        admin_key = info.get("admin_api_key", "")
        return DeviceResponse(
            device_code=device_code,
            name=info.get("name", ""),
            admin_api_key_short=admin_key[:20] + "..." if admin_key else "",
            created_at=info.get("created_at", ""),
            last_used=info.get("last_used"),
            usage_count=info.get("usage_count", 0),
        )
    
    def list_devices(self) -> DeviceListResponse:
        """获取设备列表"""
        devices = device_manager.get_all_devices()
        
        device_list = []
        for device_code, info in devices.items():
            admin_key = info.get("admin_api_key", "")
            device_list.append(DeviceResponse(
                device_code=device_code,
                name=info.get("name", ""),
                admin_api_key_short=admin_key[:20] + "..." if admin_key else "",
                created_at=info.get("created_at", ""),
                last_used=info.get("last_used"),
                usage_count=info.get("usage_count", 0),
            ))
        
        return DeviceListResponse(
            devices=device_list,
            total=len(device_list),
            api_keys_total=len(api_key_manager.load_keys()),
        )
    
    def delete_device(self, device_code: str) -> Optional[Dict]:
        """删除设备"""
        device_info = device_manager.delete_device(device_code)
        if device_info is None:
            return None
        
        admin_key = device_info.get("admin_api_key", "")
        return {
            "success": True,
            "message": f"Device {device_code} deleted",
            "freed_api_key": admin_key[:20] + "..." if admin_key else "",
        }
