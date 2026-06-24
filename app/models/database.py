"""
数据库模型定义
使用 SQLAlchemy ORM 定义用户、聊天记录和配置表
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    chat_histories = relationship("ChatHistory", back_populates="user")
    user_config = relationship("UserConfig", back_populates="user", uselist=False)


class ChatHistory(Base):
    """聊天记录表"""
    __tablename__ = "chat_histories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    model = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="chat_histories")


class UserConfig(Base):
    """用户配置表"""
    __tablename__ = "user_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    api_key = Column(String(255), default="")
    api_url = Column(String(255), default="")
    default_model = Column(String(50), default="glm-4.6v")
    mood = Column(String(20), default="happy")
    custom_models = Column(JSON, default=[])
    settings = Column(JSON, default={})
    skills = Column(JSON, default=[])
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    user = relationship("User", back_populates="user_config")


class UserStats(Base):
    """用户统计数据表"""
    __tablename__ = "user_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    daily_requests = Column(Integer, default=0)
    total_requests = Column(Integer, default=0)
    today_input_tokens = Column(Integer, default=0)
    today_output_tokens = Column(Integer, default=0)
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    tool_calls = Column(JSON, default={"get_time": 0, "calculate": 0, "get_weather": 0, "total": 0})
    daily_records = Column(JSON, default=[])
    last_reset = Column(String(20), default=datetime.now().date().isoformat())
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# 数据库连接
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
