"""
设备管理模块
负责管理ESP32设备的注册、查询和删除
"""

import json
import os
import secrets
from datetime import datetime
from typing import Dict, Optional

from .config import config


class DeviceManager:
    """设备管理器类"""
    
    def __init__(self):
        """初始化设备管理器"""
        self._devices = {}
        self._load_devices()
    
    def _load_devices(self) -> None:
        """从文件加载设备列表"""
        if os.path.exists(config.DEVICES_FILE):
            try:
                with open(config.DEVICES_FILE, "r", encoding="utf-8") as f:
                    self._devices = json.load(f)
            except Exception:
                self._devices = {}
    
    def _save_devices(self) -> None:
        """保存设备列表到文件"""
        with open(config.DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(self._devices, f, ensure_ascii=False, indent=2)
    
    def register_device(self, device_code: str, api_key: str, description: str = "") -> bool:
        """注册一个新设备"""
        if device_code in self._devices:
            return False
        
        self._devices[device_code] = {
            "api_key": api_key,
            "admin_api_key": "",
            "description": description,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "usage_count": 0
        }
        self._save_devices()
        return True
    
    def unregister_device(self, device_code: str) -> bool:
        """注销一个设备"""
        if device_code in self._devices:
            del self._devices[device_code]
            self._save_devices()
            return True
        return False
    
    def get_device(self, device_code: str) -> Optional[Dict]:
        """获取设备信息"""
        return self._devices.get(device_code)
    
    def get_all_devices(self) -> Dict:
        """获取所有设备列表"""
        return self._devices
    
    def update_device_usage(self, device_code: str, admin_api_key: str) -> bool:
        """更新设备使用信息"""
        if device_code not in self._devices:
            return False
        
        device_info = self._devices[device_code]
        device_info["last_used"] = datetime.now().isoformat()
        device_info["usage_count"] = device_info.get("usage_count", 0) + 1
        device_info["admin_api_key"] = admin_api_key
        self._save_devices()
        return True
    
    def generate_device_code(self) -> str:
        """生成一个新的设备码"""
        return secrets.token_urlsafe(16)
    
    def is_device_registered(self, device_code: str) -> bool:
        """检查设备是否已注册"""
        return device_code in self._devices


device_manager = DeviceManager()
