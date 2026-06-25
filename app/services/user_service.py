"""
用户服务模块
提供用户注册、登录、获取信息等功能
"""

import secrets as _secrets
from datetime import datetime, timedelta
from typing import Optional
import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.models.database import User, UserConfig, ChatHistory
from app.core.config import settings

# JWT 签名密钥解析优先级：
#   1. 显式配置的 JWT_SECRET_KEY（生产推荐）
#   2. 回退到 ADMIN_TOKEN（单机部署方便）
#   3. 都为空：启动随机生成并告警（重启后旧 token 全部失效，仅用于开发）
if settings.jwt_secret_key:
    SECRET_KEY = settings.jwt_secret_key
elif settings.admin_token:
    SECRET_KEY = settings.admin_token
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "未设置 JWT_SECRET_KEY，已回退使用 ADMIN_TOKEN 签名 JWT。"
        "生产环境请单独配置 JWT_SECRET_KEY 环境变量。"
    )
else:
    SECRET_KEY = _secrets.token_urlsafe(48)
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "⚠️ 未设置 JWT_SECRET_KEY / ADMIN_TOKEN，已生成临时随机密钥。"
        "重启后所有已签发的 JWT 将失效！生产环境请务必配置 JWT_SECRET_KEY。"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
# Refresh Token 有效期 7 天（详见第三阶段 F2）
REFRESH_TOKEN_EXPIRE_DAYS = 7
# Token 类型标识，用于区分 access / refresh
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return _bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return _bcrypt.hashpw(
        password.encode("utf-8"), _bcrypt.gensalt()
    ).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌（短期，默认 30 分钟）"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": TOKEN_TYPE_ACCESS})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 刷新令牌（长期，默认 7 天）。

    Refresh token 不直接用于 API 鉴权，仅用于换取新的 access token。
    详见第三阶段 F2。
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": TOKEN_TYPE_REFRESH})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """解码并验证 JWT，返回 payload 字典；失败返回 None。

    同时校验 exp 过期时间。
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_refresh_token(token: str) -> Optional[str]:
    """验证 refresh token 是否有效且类型正确。

    Returns:
        有效时返回 token 中 sub 字段（用户邮箱），无效返回 None。
    """
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        return None
    return payload.get("sub")


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """根据邮箱获取用户"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """根据用户名获取用户"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """根据ID获取用户"""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, username: str, email: str, password: str) -> User:
    """创建新用户"""
    hashed_password = get_password_hash(password)
    
    user_count = db.query(User).count()
    is_superuser = (user_count == 0)
    
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_superuser=is_superuser
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    config = UserConfig(user_id=user.id, api_key="", api_url="")
    db.add(config)
    db.commit()
    
    return user


def get_all_users(db: Session) -> list:
    """获取所有用户"""
    return db.query(User).all()


def delete_user(db: Session, user_id: int) -> bool:
    """删除用户"""
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    db.query(ChatHistory).filter(ChatHistory.user_id == user_id).delete()
    db.query(UserConfig).filter(UserConfig.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return True


def update_user(db: Session, user_id: int, **kwargs) -> Optional[User]:
    """更新用户信息"""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """验证用户身份"""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def get_user_config(db: Session, user_id: int) -> Optional[UserConfig]:
    """获取用户配置"""
    return db.query(UserConfig).filter(UserConfig.user_id == user_id).first()


def update_user_config(db: Session, user_id: int, **kwargs) -> UserConfig:
    """更新用户配置"""
    config = get_user_config(db, user_id)
    if not config:
        config = UserConfig(user_id=user_id)
        db.add(config)
    
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    db.commit()
    db.refresh(config)
    return config


def save_chat_history(db: Session, user_id: int, role: str, content: str, model: str = None):
    """保存聊天记录"""
    history = ChatHistory(
        user_id=user_id,
        role=role,
        content=content,
        model=model
    )
    db.add(history)
    db.commit()


def get_chat_history(db: Session, user_id: int, limit: int = 100) -> list:
    """获取用户聊天记录"""
    histories = db.query(ChatHistory)\
        .filter(ChatHistory.user_id == user_id)\
        .order_by(ChatHistory.created_at.desc())\
        .limit(limit)\
        .all()
    return list(reversed(histories))


def delete_chat_history(db: Session, user_id: int):
    """删除用户所有聊天记录"""
    db.query(ChatHistory)\
        .filter(ChatHistory.user_id == user_id)\
        .delete()
    db.commit()
