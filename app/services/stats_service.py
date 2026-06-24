"""
用户统计服务模块
提供用户级别的统计数据存储和查询功能
"""

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import UserStats
from app.core.stats import stats_manager


def get_user_stats(db: Session, user_id: int) -> UserStats:
    """获取用户统计数据（不存在则创建）"""
    stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
    if not stats:
        stats = UserStats(user_id=user_id)
        db.add(stats)
        db.commit()
        db.refresh(stats)
    return stats


def _rollover_if_new_day(stats: UserStats) -> bool:
    """跨天时重置每日计数"""
    today = datetime.now().date().isoformat()
    if stats.last_reset != today:
        stats.daily_requests = 0
        stats.today_input_tokens = 0
        stats.today_output_tokens = 0
        stats.last_reset = today
        return True
    return False


def increment_user_request(db: Session, user_id: int) -> None:
    """增加用户请求计数"""
    stats = get_user_stats(db, user_id)
    _rollover_if_new_day(stats)
    
    stats.daily_requests += 1
    stats.total_requests += 1
    
    today = stats.last_reset
    daily_records = stats.daily_records or []
    found = False
    for record in daily_records:
        if record.get("date") == today:
            record["count"] += 1
            found = True
            break
    if not found:
        daily_records.append({"date": today, "count": 1})
    stats.daily_records = daily_records
    
    db.commit()
    
    # 同时更新全局统计
    stats_manager.increment_request_count()


def update_user_token_usage(db: Session, user_id: int, output_tokens: int, input_tokens: int = 0) -> None:
    """更新用户 Token 使用统计"""
    stats = get_user_stats(db, user_id)
    _rollover_if_new_day(stats)
    
    stats.today_input_tokens += input_tokens
    stats.today_output_tokens += output_tokens
    stats.total_input_tokens += input_tokens
    stats.total_output_tokens += output_tokens
    
    db.commit()
    
    # 同时更新全局统计
    stats_manager.update_token_usage(output_tokens, input_tokens)


def increment_user_tool_call(db: Session, user_id: int, tool_name: str) -> None:
    """增加用户工具调用计数"""
    stats = get_user_stats(db, user_id)
    
    tool_calls = stats.tool_calls or {}
    tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1
    tool_calls["total"] = tool_calls.get("total", 0) + 1
    stats.tool_calls = tool_calls
    
    db.commit()
    
    # 同时更新全局统计
    stats_manager.increment_tool_call(tool_name)


def get_user_stats_dict(db: Session, user_id: int) -> dict:
    """获取用户统计数据字典"""
    stats = get_user_stats(db, user_id)
    _rollover_if_new_day(stats)
    db.commit()
    
    return {
        "daily_requests": stats.daily_requests,
        "total_requests": stats.total_requests,
        "today_input_tokens": stats.today_input_tokens,
        "today_output_tokens": stats.today_output_tokens,
        "total_input_tokens": stats.total_input_tokens,
        "total_output_tokens": stats.total_output_tokens,
        "tool_calls": stats.tool_calls,
        "daily_records": stats.daily_records,
    }


def get_global_stats() -> dict:
    """获取全局统计数据"""
    return stats_manager.load_stats()