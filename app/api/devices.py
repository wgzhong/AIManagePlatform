"""
设备管理 API（ESP32 设备码）。
基于数据库存储，支持用户数据隔离——每个用户只能看到和管理自己的设备。
"""

import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from app.schemas.devices import DeviceResponse, DeviceListResponse
from app.schemas.auth import MessageResponse
from app.models.database import Device, get_db
from app.api.auth_deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/devices/register")
def register_device(
    device_name: str = Form(default="Hardware Device"),
    admin_api_key: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """注册新设备，绑定到当前登录用户"""
    logger.info(f"[设备注册] 用户={current_user.username}(id={current_user.id}), 设备名={device_name}, key长度={len(admin_api_key) if admin_api_key else 0}")

    # 验证 API Key
    if not admin_api_key or len(admin_api_key.strip()) < 10:
        logger.warning(f"[设备注册] API Key 无效: 长度={len(admin_api_key) if admin_api_key else 0}")
        raise HTTPException(status_code=400, detail="请提供有效的 API Key（至少10位字符）")

    # 生成不重复的 8 位 hex 设备码
    device_code = _generate_device_code(db)

    try:
        device = Device(
            user_id=current_user.id,
            device_code=device_code,
            device_name=device_name.strip(),
            admin_api_key=admin_api_key.strip(),
            usage_count=0,
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        logger.info(f"[设备注册] ✅ 成功: code={device_code}, name={device_name}")

        return {
            "success": True,
            "device_code": device_code,
            "device_name": device_name,
            "message": f"设备 {device_code} 注册成功",
        }
    except Exception as e:
        db.rollback()
        logger.error(f"[设备注册] ❌ 数据库写入失败: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"数据库写入失败：{str(e)}")


@router.get("/api/devices", response_model=DeviceListResponse)
def list_devices(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """列出当前用户已注册的设备（仅自己的）"""
    devices = (
        db.query(Device)
        .filter(Device.user_id == current_user.id)
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

    return DeviceListResponse(devices=device_list, total=len(device_list), api_keys_total=0)


@router.delete("/api/devices/{device_code}", response_model=MessageResponse)
def delete_device(
    device_code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除当前用户的指定设备（只能删自己的）"""
    device = (
        db.query(Device)
        .filter(Device.device_code == device_code, Device.user_id == current_user.id)
        .first()
    )
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在或无权操作")

    db.delete(device)
    db.commit()
    return MessageResponse(message=f"设备 {device_code} 已删除")


@router.get("/api/devices/{device_code}", response_model=DeviceResponse)
def get_device(
    device_code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取当前用户的指定设备信息（只能查看自己的）"""
    device = (
        db.query(Device)
        .filter(Device.device_code == device_code, Device.user_id == current_user.id)
        .first()
    )
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在或无权操作")

    return DeviceResponse(
        device_code=device.device_code,
        name=device.device_name,
        admin_api_key_short=device.admin_api_key[:20] + "..." if device.admin_api_key else "",
        created_at=device.created_at.isoformat() if device.created_at else "",
        last_used=device.last_used.isoformat() if device.last_used else None,
        usage_count=device.usage_count or 0,
    )


def _generate_device_code(db: Session) -> str:
    """生成不重复的 8 位 hex 设备码"""
    for _ in range(100):
        code = secrets.token_hex(4).upper()
        exists = db.query(Device.device_code).filter(Device.device_code == code).first()
        if not exists:
            return code
    raise RuntimeError("无法生成唯一设备码")
