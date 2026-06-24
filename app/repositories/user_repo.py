"""
用户 Repository
封装 User / UserConfig 的数据访问操作。
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.database import User, UserConfig
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """用户数据访问层"""

    model = User

    def get_by_email(self, email: str) -> Optional[User]:
        """按邮箱查询"""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """按用户名查询"""
        return self.db.query(User).filter(User.username == username).first()

    def get_active_users(self) -> List[User]:
        """获取活跃用户列表"""
        return self.db.query(User).filter(User.is_active == True).all()  # noqa: E712


class UserConfigRepository(BaseRepository[UserConfig]):
    """用户配置数据访问层"""

    model = UserConfig

    def get_by_user_id(self, user_id: int) -> Optional[UserConfig]:
        """按用户 ID 获取配置"""
        return self.db.query(UserConfig).filter(UserConfig.user_id == user_id).first()

    def get_or_create(self, user_id: int, defaults: dict = None) -> UserConfig:
        """获取或创建用户配置"""
        config = self.get_by_user_id(user_id)
        if not config:
            config = self.create(user_id=user_id, **(defaults or {}))
        return config

    def update_by_user_id(self, user_id: int, **kwargs) -> Optional[UserConfig]:
        """按用户 ID 更新配置"""
        config = self.get_by_user_id(user_id)
        if not config:
            config = self.create(user_id=user_id)
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        self.db.commit()
        self.db.refresh(config)
        return config
