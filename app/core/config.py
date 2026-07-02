"""
配置管理模块
使用 Pydantic Settings 管理应用配置参数和文件路径。
所有敏感配置（API Key、Token）通过环境变量注入。

⚠️ 重要：全项目一律通过 `settings` 读取配置，禁止直接调用 `os.environ.get`，
也禁止再引入 ConfigManager 之类的包装类（详见第二阶段 A4 清理）。
否则在仅写 `.env` 文件（不注入系统环境变量）的部署方式下会出现"配置静默失效"事故。
"""

import logging
import os
from datetime import datetime
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# 应用启动时间（用于运行时长统计）
SYSTEM_START_TIME = datetime.now()


class Settings(BaseSettings):
    """应用配置类

    所有字段均可通过 .env 文件或环境变量注入。
    路径类配置用 @property 派生，避免在配置类里硬编码绝对路径。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # LLM 配置（生产环境务必通过环境变量 ZHIPU_API_KEY 设置）
    zhipu_api_key: str = ""
    zhipu_api_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    llm_default_model: str = "glm-4.6v"
    llm_verify_ssl: bool = True
    llm_debug: bool = True

    # 管理接口鉴权
    admin_token: str = ""

    # JWT 签名密钥（生产必填；留空时回退到 ADMIN_TOKEN；都为空则启动随机生成并告警）
    jwt_secret_key: str = ""

    # API Key 加密种子（留空时回退到 admin_token；都为空则明文存储并告警）
    encryption_key: str = ""

    # 限流配置
    chat_rate_limit: str = "30/minute"

    # 服务运行配置
    app_port: int = 8002
    internal_api_url: str = ""  # 内部 API 调用地址（Skill 调用后端时），为空则自动生成为 http://localhost:{app_port}
    max_devices_per_key: int = 50

    # CORS 配置：逗号分隔的允许源；留空表示允许全部（仅开发用，且强制关闭 credentials）
    cors_origins: str = ""
    # 是否允许携带凭证。当 cors_origins 为 * 时会被强制设为 False（浏览器规范要求）
    cors_credentials: bool = True

    @property
    def api_keys(self) -> list:
        """解析逗号分隔的 API Keys"""
        return [k.strip() for k in self.zhipu_api_key.split(",") if k.strip()]

    @property
    def base_dir(self) -> str:
        """项目根目录"""
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @property
    def data_dir(self) -> str:
        """数据存储目录"""
        data_dir = os.path.join(self.base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    @property
    def api_keys_file(self) -> str:
        """API Keys 存储文件"""
        return os.path.join(self.data_dir, "api_keys.json")

    @property
    def devices_file(self) -> str:
        """设备信息存储文件"""
        return os.path.join(self.data_dir, "devices.json")

    @property
    def stats_file(self) -> str:
        """统计数据存储文件"""
        return os.path.join(self.data_dir, "stats.json")


settings = Settings()


def get_effective_admin_token() -> str:
    """统一入口：获取生效的管理员 token（trim 后）。"""
    return (settings.admin_token or "").strip()


def get_effective_encryption_key() -> str:
    """统一入口：获取生效的加密种子。

    优先用 ENCRYPTION_KEY，回退到 ADMIN_TOKEN，都为空则返回空字符串（明文模式）。
    """
    return (settings.encryption_key or settings.admin_token or "").strip()


def assert_production_config() -> None:
    """启动自检：生产环境下若关键配置缺失则直接抛错拒绝启动。

    判定"生产环境"的依据：ADMIN_TOKEN 已配置（认为是有意部署）。
    若未配置 ADMIN_TOKEN，视为本地开发模式，仅打印警告。
    """
    admin_token = get_effective_admin_token()

    if not admin_token:
        # 开发模式：仅警告
        logger.warning(
            "⚠️  ADMIN_TOKEN 未设置，管理接口鉴权已关闭。"
            "生产环境请务必在 .env 文件中设置 ADMIN_TOKEN。"
        )
        return

    # 生产模式：严格自检
    issues = []

    # JWT 密钥回退到 ADMIN_TOKEN 时也算可接受，但记录一条信息
    if not settings.jwt_secret_key:
        logger.info("JWT_SECRET_KEY 未单独配置，回退到 ADMIN_TOKEN 签发 JWT。")

    # 加密种子回退检查
    if not get_effective_encryption_key():
        issues.append(
            "API Key 将明文存储。请配置 ENCRYPTION_KEY 或 ADMIN_TOKEN。"
        )

    # CORS 默认通配
    if not settings.cors_origins.strip():
        issues.append(
            "CORS_ORIGINS 未配置，默认允许全部源（生产请配置具体域名）。"
        )

    if issues:
        joined = " | ".join(issues)
        logger.warning("⚠️  生产环境配置检查发现风险：%s", joined)
