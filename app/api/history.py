"""
对话历史 API。
基于 SQLite 数据库查询，移除旧的 JSON Lines+gzip 文件存储依赖。
"""

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.models.database import ChatHistory, get_db
from app.middleware.auth import require_admin

router = APIRouter()


@router.get("/api/chat/history")
async def get_chat_history(db: Session = Depends(get_db)):
    """获取全部用户对话历史（最近1000条）"""
    histories = (
        db.query(ChatHistory)
        .order_by(ChatHistory.created_at.desc())
        .limit(1000)
        .all()
    )
    return {
        "history": [
            {
                "role": h.role,
                "content": h.content,
                "model": h.model,
                "user_id": h.user_id,
                "created_at": h.created_at.isoformat() if h.created_at else "",
            }
            for h in reversed(histories)
        ]
    }


@router.delete("/api/chat/history")
async def clear_chat_history(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """清空全部对话历史（需 admin 鉴权）"""
    db.query(ChatHistory).delete()
    db.commit()
    return {"success": True}
