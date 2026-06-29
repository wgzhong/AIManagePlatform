"""
外部 API Key 管理服务
负责第三方密钥的 CRUD + 加密/脱敏
"""

import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from app.models.database import ExternalApiKey, get_db
from app.core.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)

# 预置分类定义（与 schemas 共享）
CATEGORIES = {
    "llm": {"label": "大模型 LLM", "icon": "🤖", "color": "#72e0e0"},
    "weather": {"label": "天气服务", "icon": "🌤️", "color": "#4ade80"},
    "navigation": {"label": "导航地图", "icon": "🗺️", "color": "#fb923c"},
    "search": {"label": "搜索引擎", "icon": "🔍", "color": "#a78bfa"},
    "translation": {"label": "翻译服务", "icon": "🌐", "color": "#f472b6"},
    "storage": {"label": "云存储", "icon": "☁️", "color": "#38bdf8"},
    "notification": {"label": "消息推送", "icon": "📬", "color": "#facc15"},
    "other": {"label": "其他", "icon": "🔑", "color": "#9898aa"},
}


class ProviderKeyService:
    """外部 API Key 服务"""

    @staticmethod
    def _mask_key(plain_key: str) -> str:
        """密钥脱敏：显示前4位和后4位，中间用 **** 代替"""
        if len(plain_key) <= 12:
            return plain_key[:2] + "****" + plain_key[-2:] if len(plain_key) > 4 else "****"
        return plain_key[:4] + "****" + plain_key[-4:]

    def list_keys(self, db: Session, category: Optional[str] = None) -> Tuple[List[dict], dict]:
        """列出所有 Key，按分类和优先级排序"""
        query = db.query(ExternalApiKey)
        if category and category != "all":
            query = query.filter(ExternalApiKey.category == category)
        records = query.order_by(
            ExternalApiKey.category,
            ExternalApiKey.priority.desc(),
            ExternalApiKey.id
        ).all()

        items = []
        cat_stats = {}
        for r in records:
            try:
                plain = decrypt(r.key_value)
            except Exception:
                plain = r.key_value  # 解密失败则显示原值
            items.append({
                "id": r.id,
                "provider_name": r.provider_name,
                "provider_code": r.provider_code,
                "category": r.category,
                "key_masked": self._mask_key(plain),
                "api_url": r.api_url or "",
                "models": r.models or [],
                "is_active": r.is_active,
                "priority": r.priority,
                "description": r.description or "",
                "config": r.config or {},
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            })
            # 统计分类
            cat_stats[r.category] = cat_stats.get(r.category, 0) + 1
        return items, cat_stats

    def get_key(self, db: Session, key_id: int) -> Optional[dict]:
        """获取单个 Key 详情（含完整密文用于编辑）"""
        record = db.query(ExternalApiKey).filter(ExternalApiKey.id == key_id).first()
        if not record:
            return None
        return {
            "id": record.id,
            "provider_name": record.provider_name,
            "provider_code": record.provider_code,
            "category": record.category,
            "key_value": record.key_value,   # 加密后的密文（前端回显时解密）
            "api_url": record.api_url or "",
            "models": record.models or [],
            "is_active": record.is_active,
            "priority": record.priority,
            "description": record.description or "",
            "config": record.config or {},
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "updated_at": record.updated_at.isoformat() if record.updated_at else "",
        }

    def create_key(self, db: Session, data: dict) -> dict:
        """新增 Key（自动加密）"""
        encrypted = encrypt(data["key_value"])
        record = ExternalApiKey(
            provider_name=data["provider_name"],
            provider_code=data["provider_code"],
            category=data.get("category", "other"),
            key_value=encrypted,
            api_url=data.get("api_url", ""),
            models=data.get("models", []),
            is_active=data.get("is_active", True),
            priority=data.get("priority", 0),
            description=data.get("description", ""),
            config=data.get("config", {}),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info("创建外部API Key: %s (%s)", data["provider_code"], data["category"])
        return {"id": record.id, "provider_code": data["provider_code"], "message": "创建成功"}

    def update_key(self, db: Session, key_id: int, data: dict) -> dict:
        """更新 Key（如果 key_value 有变化则重新加密）"""
        record = db.query(ExternalApiKey).filter(ExternalApiKey.id == key_id).first()
        if not record:
            return None

        record.provider_name = data.get("provider_name", record.provider_name)
        record.provider_code = data.get("provider_code", record.provider_code)
        record.category = data.get("category", record.category)
        record.api_url = data.get("api_url", record.api_url)
        record.models = data.get("models", record.models)
        record.is_active = data.get("is_active", record.is_active)
        record.priority = data.get("priority", record.priority)
        record.description = data.get("description", record.description)
        record.config = data.get("config", record.config or {})

        # 如果传了新的 key_value 则重新加密
        if "key_value" in data and data["key_value"]:
            record.key_value = encrypt(data["key_value"])

        db.commit()
        db.refresh(record)
        logger.info("更新外部API Key id=%d: %s", key_id, data.get("provider_code"))
        return {"id": record.id, "message": "更新成功"}

    def delete_key(self, db: Session, key_id: int) -> bool:
        """删除 Key"""
        record = db.query(ExternalApiKey).filter(ExternalApiKey.id == key_id).first()
        if not record:
            return False
        code = record.provider_code
        db.delete(record)
        db.commit()
        logger.info("删除外部API Key id=%d: %s", key_id, code)
        return True

    def toggle_active(self, db: Session, key_id: int) -> Optional[dict]:
        """切换启用/禁用状态"""
        record = db.query(ExternalApiKey).filter(ExternalApiKey.id == key_id).first()
        if not record:
            return None
        record.is_active = not record.is_active
        db.commit()
        return {"id": record.id, "is_active": record.is_active}

    def get_by_category(self, db: Session, category: str) -> List[dict]:
        """获取某分类下所有启用的 Key 的明文（供业务调用）"""
        records = db.query(ExternalApiKey).filter(
            ExternalApiKey.category == category,
            ExternalApiKey.is_active == True
        ).order_by(ExternalApiKey.priority.desc()).all()
        result = []
        for r in records:
            try:
                plain = decrypt(r.key_value)
            except Exception:
                continue
            result.append({
                "id": r.id,
                "provider_code": r.provider_code,
                "provider_name": r.provider_name,
                "key_value": plain,
                "api_url": r.api_url or "",
                "models": r.models or [],
            })
        return result

    def test_connection(self, db: Session, key_id: int) -> dict:
        """测试 Key 是否可用（简单验证非空且格式合理）"""
        record = db.query(ExternalApiKey).filter(ExternalApiKey.id == key_id).first()
        if not record:
            return {"success": False, "error": "Key 不存在"}
        try:
            plain = decrypt(record.key_value)
        except Exception as e:
            return {"success": False, "error": f"解密失败: {e}"}
        if not plain or len(plain) < 4:
            return {"success": False, "error": "Key 值无效或过短"}
        # TODO: 可针对具体分类做实际 HTTP 探测
        return {
            "success": True,
            "message": f"{record.provider_name} 密钥格式验证通过",
            "masked": self._mask_key(plain),
        }
