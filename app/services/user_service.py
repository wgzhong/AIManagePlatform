"""
用户服务模块
提供用户注册、登录、获取信息等功能
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.database import User, UserConfig, ChatHistory
from app.core.config import settings

# JWT配置
SECRET_KEY = settings.admin_token or "your-secret-key-keep-it-safe"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


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
