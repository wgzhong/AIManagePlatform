"""
Repository 基类
提供通用的 CRUD 操作方法模板，子类继承后自动获得基本数据操作能力。
"""

from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy.orm import Session

from app.models.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """通用 Repository 基类，提供标准 CRUD 操作"""

    model: Type[T]  # 子类必须覆写

    def __init__(self, db: Session):
        self.db = db

    # ── 查询 ──

    def get_by_id(self, entity_id: Any) -> Optional[T]:
        """按主键查询"""
        return self.db.query(self.model).get(entity_id)

    def get_all(self) -> List[T]:
        """查询全部"""
        return self.db.query(self.model).all()

    def count(self) -> int:
        """计数"""
        return self.db.query(self.model).count()

    # ── 创建 ──

    def create(self, **kwargs) -> T:
        """新建记录并 commit"""
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    # ── 更新 ──

    def update(self, entity_id: Any, **kwargs) -> Optional[T]:
        """按 ID 更新字段"""
        obj = self.get_by_id(entity_id)
        if not obj:
            return None
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    # ── 删除 ──

    def delete(self, entity_id: Any) -> bool:
        """按 ID 删除"""
        obj = self.get_by_id(entity_id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
