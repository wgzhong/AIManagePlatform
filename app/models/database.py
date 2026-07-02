"""
数据库模型定义
使用 SQLAlchemy ORM 定义用户、聊天记录和配置表
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Index
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
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
    last_reset = Column(String(20), default=lambda: datetime.now().date().isoformat())
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserSkill(Base):
    """用户私人技能表（贡献开关控制存数据库还是 skills/ 文件夹）"""
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, default="")
    category = Column(String(50), default="自定义")
    icon = Column(String(20), default="🔧")
    enabled = Column(Boolean, default=True)
    auto_trigger = Column(Boolean, default=False)
    trigger_keywords = Column(JSON, default=[])
    system_prompt = Column(Text, default="")
    is_contributed = Column(Boolean, default=False)
    contributed_skill_path = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User")


class Device(Base):
    """ESP32 设备管理表（替代 devices.json）"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_code = Column(String(20), unique=True, nullable=False, index=True)
    device_name = Column(String(100), nullable=False)
    admin_api_key = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    last_used = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)

    user = relationship("User")

    __table_args__ = {"sqlite_autoincrement": True}


class ExternalApiKey(Base):
    """外部服务 API Key 管理表（大模型/天气/导航等第三方密钥）"""
    __tablename__ = "external_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String(100), nullable=False)          # 显示名称：如 "智谱 AI"、"OpenAI"
    provider_code = Column(String(50), nullable=False, index=True)  # 唯一标识：如 "zhipu"、"openai"
    category = Column(String(30), nullable=False, index=True)     # 分类：llm / weather / navigation / search / other
    key_value = Column(Text, nullable=False)                      # 加密后的密文
    api_url = Column(String(500), default="")                     # API 地址（可选）
    models = Column(JSON, default=[])                             # 关联模型列表（LLM 类专用）
    is_active = Column(Boolean, default=True)                     # 是否启用
    priority = Column(Integer, default=0)                         # 优先级
    description = Column(Text, default="")                        # 备注
    config = Column(JSON, default={})                            # 额外配置（天气/导航等分类专属配置）
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (Index("idx_provider_code_unique", "provider_code", unique=True),)



import os as _os
_data_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "data")
_os.makedirs(_data_dir, exist_ok=True)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_data_dir}/app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """初始化数据库表（含自适应列迁移）"""
    Base.metadata.create_all(bind=engine)
    # 自适应迁移：给 devices 表添加 user_id 列（如果不存在）
    _ensure_device_user_id_column()
    # 自适应迁移：给 external_api_keys 表添加 config 列
    _ensure_external_api_key_config_column()

def _ensure_device_user_id_column():
    """确保 devices 表有 user_id 列，没有则 ALTER TABLE 添加。
    SQLite ALTER TABLE 不支持 REFERENCES 子句，外键约束仅在建表时生效。
    """
    import sqlite3, os, logging
    logger = logging.getLogger(__name__)
    db_path = os.path.join(_data_dir, "app.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(devices)")
        columns = {row[1] for row in cursor.fetchall()}
        if "user_id" not in columns:
            # SQLite ALTER TABLE 不支持 REFERENCES，仅添加列
            conn.execute(
                "ALTER TABLE devices ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"
            )
            conn.commit()
            logger.info("✅ devices 表已添加 user_id 列，旧数据默认归用户 id=1")
    finally:
        conn.close()


def _ensure_external_api_key_config_column():
    """确保 external_api_keys 表有 config 列，没有则 ALTER TABLE 添加。"""
    import sqlite3, os, logging
    logger = logging.getLogger(__name__)
    db_path = os.path.join(_data_dir, "app.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(external_api_keys)")
        columns = {row[1] for row in cursor.fetchall()}
        if "config" not in columns:
            conn.execute("ALTER TABLE external_api_keys ADD COLUMN config TEXT DEFAULT '{}'")
            conn.commit()
            logger.info("✅ external_api_keys 表已添加 config 列")
    finally:
        conn.close()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
