"""
JWT Token 黑名单机制。

提供 in-memory 黑名单存储（生产环境建议使用 Redis）。
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory 黑名单存储（token: 过期时间）
# 生产环境应迁移到 Redis 或其他持久化存储
_BLACKLIST: dict[str, datetime] = {}


def add_to_blacklist(token: str) -> None:
    """将 token 加入黑名单"""
    from jose import jwt
    from app.services.user_service import SECRET_KEY, ALGORITHM
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # 存储 token 及其过期时间
        exp = payload.get("exp")
        if exp:
            from datetime import datetime, timezone
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
            _BLACKLIST[token] = exp_dt
        else:
            # 无过期时间的 token 存储为 None（永不过期）
            _BLACKLIST[token] = None
        logger.info("Token 已加入黑名单")
    except Exception:
        # Token 解码失败（可能已过期或伪造），但仍加入黑名单
        # 使用 None 表示永不过期（将在下次 cleanup 时手动清理或重启后消失）
        _BLACKLIST[token] = None
        logger.info("Token 已加入黑名单（解码失败，可能是过期/伪造的 token）")


def is_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中"""
    return token in _BLACKLIST


def cleanup_expired() -> None:
    """清理已过期的黑名单 token（应在每次 logout 时调用）"""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    expired = [
        token for token, exp in _BLACKLIST.items()
        if exp is not None and exp < now
    ]
    for token in expired:
        del _BLACKLIST[token]
    if expired:
        logger.info("清理了 %d 个过期的黑名单 token", len(expired))


def periodic_cleanup() -> None:
    """供后台任务调用的周期性清理（可选）"""
    cleanup_expired()
