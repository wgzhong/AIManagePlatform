"""
设备服务模块
封装设备管理业务逻辑，基于 SQLAlchemy 数据库（支持用户数据隔离）
"""

import secrets
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.database import Device
from app.schemas.devices import DeviceResponse, DeviceListResponse


class DeviceService:
    """设备服务类——支持按用户隔离"""

    def register_device(
        self,
        db: Session,
        user_id: int,
        device_name: str,
        admin_api_key: str,
    ) -> dict:
        """注册新设备，绑定到当前用户"""
        if not admin_api_key or len(admin_api_key) < 10:
            return {
                "success": False,
                "error": "请提供有效的 API Key",
                "message": "请在首页输入您的 API Key 后再注册设备",
            }

        # 生成不重复的 8 位 hex 设备码
        device_code = self._generate_device_code(db)

        device = Device(
            user_id=user_id,
            device_code=device_code,
            device_name=device_name,
            admin_api_key=admin_api_key,
            usage_count=0,
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        return {
            "success": True,
            "device_code": device_code,
            "device_name": device_name,
            "message": f"设备注册成功！设备码：{device_code}",
        }

    def get_device(self, db: Session, user_id: int, device_code: str) -> Optional[DeviceResponse]:
        """获取当前用户的设备信息"""
        device = (
            db.query(Device)
            .filter(Device.device_code == device_code, Device.user_id == user_id)
            .first()
        )
        if device is None:
            return None

        return DeviceResponse(
            device_code=device.device_code,
            name=device.device_name,
            admin_api_key_short=device.admin_api_key[:20] + "..." if device.admin_api_key else "",
            created_at=device.created_at.isoformat() if device.created_at else "",
            last_used=device.last_used.isoformat() if device.last_used else None,
            usage_count=device.usage_count or 0,
        )

    def list_devices(self, db: Session, user_id: int) -> DeviceListResponse:
        """获取当前用户的设备列表"""
        devices = (
            db.query(Device)
            .filter(Device.user_id == user_id)
            .order_by(Device.created_at.desc())
            .all()
        )

        device_list = [
            DeviceResponse(
                device_code=d.device_code,
                name=d.device_name,
                admin_api_key_short=d.admin_api_key[:20] + "..." if d.admin_api_key else "",
                created_at=d.created_at.isoformat() if d.created_at else "",
                last_used=d.last_used.isoformat() if d.last_used else None,
                usage_count=d.usage_count or 0,
            )
            for d in devices
        ]

        return DeviceListResponse(
            devices=device_list,
            total=len(device_list),
            api_keys_total=0,  # 不再从 api_key_manager 统一读取
        )

    def delete_device(self, db: Session, user_id: int, device_code: str) -> Optional[Dict]:
        """删除当前用户的设备"""
        device = (
            db.query(Device)
            .filter(Device.device_code == device_code, Device.user_id == user_id)
            .first()
        )
        if device is None:
            return None

        freed_key = device.admin_api_key[:20] + "..." if device.admin_api_key else ""
        db.delete(device)
        db.commit()

        return {
            "success": True,
            "message": f"Device {device_code} deleted",
            "freed_api_key": freed_key,
        }

    def update_usage(self, db: Session, device_code: str) -> bool:
        """更新设备使用信息（供 ESP32 调用，不需要用户鉴权）"""
        device = db.query(Device).filter(Device.device_code == device_code).first()
        if not device:
            return False

        device.last_used = datetime.now()
        device.usage_count = (device.usage_count or 0) + 1
        db.commit()
        return True

    @staticmethod
    def _generate_device_code(db: Session) -> str:
        """生成不重复的 8 位 hex 设备码"""
        for _ in range(100):  # 防止无限循环
            code = secrets.token_hex(4).upper()
            exists = db.query(Device.device_code).filter(Device.device_code == code).first()
            if not exists:
                return code
        raise RuntimeError("无法生成唯一设备码")
