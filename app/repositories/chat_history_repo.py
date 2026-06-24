"""
聊天历史 Repository
封装 ChatHistory 的数据访问操作。
"""

from typing import List, Optional
from datetime import datetime

from app.models.database import ChatHistory
from .base import BaseRepository


class ChatHistoryRepository(BaseRepository[ChatHistory]):
    """聊天历史数据访问层"""

    model = ChatHistory

    def get_by_user_id(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> List[ChatHistory]:
        """按用户 ID 获取聊天记录（按时间倒序）"""
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def add_message(
        self, user_id: int, role: str, content: str, model: str = None
    ) -> ChatHistory:
        """添加一条聊天消息"""
        return self.create(
            user_id=user_id,
            role=role,
            content=content,
            model=model,
            created_at=datetime.now(),
        )

    def delete_by_user_id(self, user_id: int) -> int:
        """删除用户所有聊天记录，返回删除条数"""
        count = (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id)
            .delete()
        )
        self.db.commit()
        return count

    def get_recent(self, limit: int = 1000) -> List[ChatHistory]:
        """获取最近的全部聊天记录"""
        return (
            self.db.query(ChatHistory)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
            .all()
        )

    def delete_all(self) -> int:
        """清空所有聊天记录，返回删除条数"""
        count = self.db.query(ChatHistory).delete()
        self.db.commit()
        return count
