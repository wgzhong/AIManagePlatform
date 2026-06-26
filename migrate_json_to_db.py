"""
数据库迁移脚本：从 JSON 文件迁移到 SQLite 数据库。

运行方式：
    python migrate_json_to_db.py
"""

import json
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_devices():
    """将 devices.json 迁移到 devices 表"""
    from app.models.database import SessionLocal, Device, Base, engine

    # 确保表存在
    Base.metadata.create_all(bind=engine)

    devices_file = "data/devices.json"
    if not os.path.exists(devices_file):
        logger.info("devices.json 不存在，跳过迁移")
        return

    with open(devices_file, "r", encoding="utf-8") as f:
        devices_data = json.load(f)

    db = SessionLocal()
    try:
        count = 0
        for device_code, info in devices_data.items():
            # 检查是否已存在
            existing = db.query(Device).filter(Device.device_code == device_code).first()
            if existing:
                logger.info("设备 %s 已存在，跳过", device_code)
                continue

            device = Device(
                device_code=device_code,
                device_name=info.get("name", ""),
                admin_api_key=info.get("admin_api_key", ""),
                created_at=datetime.fromisoformat(info.get("created_at")) if info.get("created_at") else None,
                last_used=datetime.fromisoformat(info.get("last_used")) if info.get("last_used") else None,
                usage_count=info.get("usage_count", 0),
            )
            db.add(device)
            count += 1

        db.commit()
        logger.info("✅ 成功迁移 %d 个设备到数据库", count)
    except Exception as e:
        db.rollback()
        logger.error("❌ 迁移设备失败: %s", e)
    finally:
        db.close()


def migrate_stats():
    """将 stats.json 迁移到 user_stats 表"""
    from app.models.database import SessionLocal, UserStats, Base, engine, User

    # 确保表存在
    Base.metadata.create_all(bind=engine)

    stats_file = "data/stats.json"
    if not os.path.exists(stats_file):
        logger.info("stats.json 不存在，跳过迁移")
        return

    with open(stats_file, "r", encoding="utf-8") as f:
        stats_data = json.load(f)

    db = SessionLocal()
    try:
        count = 0
        for user_id_str, data in stats_data.items():
            user_id = int(user_id_str)

            # 检查用户是否存在
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning("用户 %d 不存在，跳过", user_id)
                continue

            # 检查统计记录是否已存在
            existing = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            if existing:
                logger.info("用户 %d 的统计记录已存在，跳过", user_id)
                continue

            stats = UserStats(
                user_id=user_id,
                daily_requests=data.get("daily_requests", 0),
                total_requests=data.get("total_requests", 0),
                today_input_tokens=data.get("today_input_tokens", 0),
                today_output_tokens=data.get("today_output_tokens", 0),
                total_input_tokens=data.get("total_input_tokens", 0),
                total_output_tokens=data.get("total_output_tokens", 0),
                tool_calls=data.get("tool_calls", {}),
                daily_records=data.get("daily_records", []),
                last_reset=data.get("last_reset", ""),
            )
            db.add(stats)
            count += 1

        db.commit()
        logger.info("✅ 成功迁移 %d 个用户的统计数据到数据库", count)
    except Exception as e:
        db.rollback()
        logger.error("❌ 迁移统计数据失败: %s", e)
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("开始迁移数据...")
    migrate_devices()
    migrate_stats()
    logger.info("迁移完成！")
