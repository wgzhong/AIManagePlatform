"""
Repository 模式层
提供统一的数据访问抽象，隔离 ORM 细节。
所有数据库操作通过 Repository 进行，不直接在 Service 层使用 SQLAlchemy Session。
"""

from .base import BaseRepository
from .user_repo import UserRepository
from .chat_history_repo import ChatHistoryRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "ChatHistoryRepository",
]
