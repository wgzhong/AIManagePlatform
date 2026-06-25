"""
用户聊天历史与统计 API。
（拆分自原 auth.py，第三阶段 F1/F3 重构）
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.user_service import get_chat_history, delete_chat_history
from app.api.auth_deps import get_current_user
from app.schemas.user import ChatHistoryItem, UserStatsResponse
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/auth", tags=["user-history"])


@router.get("/history", response_model=List[ChatHistoryItem])
def get_history(
    limit: int = 100,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户聊天记录"""
    histories = get_chat_history(db, current_user.id, limit)
    return [
        ChatHistoryItem(
            role=h.role,
            content=h.content,
            model=h.model,
            created_at=h.created_at.isoformat() if h.created_at else "",
        )
        for h in histories
    ]


@router.delete("/history", response_model=MessageResponse)
def clear_history(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """清空用户聊天记录"""
    delete_chat_history(db, current_user.id)
    return MessageResponse(message="聊天记录已清空")


@router.get("/stats", response_model=UserStatsResponse)
def get_user_stats(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户的统计数据（含全局设备信息）"""
    from app.services.stats_service import get_user_stats_dict
    from app.core.devices import device_manager
    import logging

    logger = logging.getLogger(__name__)
    stats = get_user_stats_dict(db, current_user.id)

    # 添加全局设备统计
    try:
        all_devices = device_manager.get_all_devices()
        stats["online_devices"] = 0  # 当前无在线状态跟踪
        stats["total_devices"] = len(all_devices)
    except Exception:
        logger.exception("获取设备统计失败")
        stats["online_devices"] = 0
        stats["total_devices"] = 0

    return UserStatsResponse(**stats)
