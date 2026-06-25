"""
设备管理模块
负责管理ESP32设备的注册、查询和删除

⚠️ 并发安全：所有读写 self._devices 的方法都通过 self._lock 保护，
防止多请求并发导致 devices.json 损坏或 usage_count 丢失（详见 P0-2 修复）。
"""

import json
import logging
import os
import secrets
import threading
from datetime import datetime
from typing import Dict, Optional

from .config import settings

logger = logging.getLogger(__name__)


class DeviceManager:
    """设备管理器类"""

    def __init__(self):
        """初始化设备管理器"""
        self._devices = {}
        # 用 threading.Lock 保护同步文件 I/O；这是单例，所有请求共享同一把锁
        self._lock = threading.Lock()
        self._load_devices()

    def _load_devices(self) -> None:
        """从文件加载设备列表"""
        with self._lock:
            if os.path.exists(settings.devices_file):
                try:
                    with open(settings.devices_file, "r", encoding="utf-8") as f:
                        self._devices = json.load(f)
                except Exception as e:
                    logger.warning("加载设备列表失败: %s", e)
                    self._devices = {}

    def _save_devices(self) -> None:
        """保存设备列表到文件（调用方应已持有 _lock）"""
        with open(settings.devices_file, "w", encoding="utf-8") as f:
            json.dump(self._devices, f, ensure_ascii=False, indent=2)

    def register_device(self, device_name: str, admin_api_key: str) -> Dict:
        """
        注册一个新设备，自动生成不重复的设备码并绑定管理员 API Key。
        """
        with self._lock:
            # 生成 8 位 hex 设备码，确保不重复
            device_code = secrets.token_hex(4).upper()
            while device_code in self._devices:
                device_code = secrets.token_hex(4).upper()

            self._devices[device_code] = {
                "name": device_name,
                "admin_api_key": admin_api_key,
                "created_at": datetime.now().isoformat(),
                "last_used": None,
                "usage_count": 0,
            }
            self._save_devices()
            return {"device_code": device_code, "device_name": device_name}

    def delete_device(self, device_code: str) -> Optional[Dict]:
        """删除设备，返回被删除的设备信息（不存在则 None）"""
        with self._lock:
            if device_code in self._devices:
                info = self._devices.pop(device_code)
                self._save_devices()
                return info
            return None

    def get_device(self, device_code: str) -> Optional[Dict]:
        """获取设备信息（只读，仍加锁避免读到半写状态）"""
        with self._lock:
            # 返回拷贝避免外部修改污染内存
            info = self._devices.get(device_code)
            return dict(info) if info else None

    def get_all_devices(self) -> Dict:
        """获取所有设备列表（返回浅拷贝避免外部修改）"""
        with self._lock:
            return {k: dict(v) for k, v in self._devices.items()}

    def update_device_usage(self, device_code: str, admin_api_key: str) -> bool:
        """更新设备使用信息（线程安全）"""
        with self._lock:
            if device_code not in self._devices:
                return False

            device_info = self._devices[device_code]
            device_info["last_used"] = datetime.now().isoformat()
            device_info["usage_count"] = device_info.get("usage_count", 0) + 1
            device_info["admin_api_key"] = admin_api_key
            self._save_devices()
            return True


device_manager = DeviceManager()
