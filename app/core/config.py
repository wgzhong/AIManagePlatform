"""
配置管理模块
使用 Pydantic Settings 管理应用配置参数和文件路径。
所有敏感配置（API Key、Token）通过环境变量注入。
"""

import os
from datetime import datetime
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # LLM 配置
    zhipu_api_key: str = "your_api_key_1"
    zhipu_api_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    llm_default_model: str = "glm-5.1"
    llm_verify_ssl: bool = True
    llm_debug: bool = False
    
    # 管理接口鉴权
    admin_token: str = ""
    
    # 限流配置
    chat_rate_limit: str = "30/minute"
    
    # 服务运行配置
    app_port: int = 8002
    max_devices_per_key: int = 50
    max_chat_history_size: int = 10 * 1024 * 1024
    
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
    
    @property
    def chat_history_file(self) -> str:
        """聊天历史存储文件"""
        return os.path.join(self.data_dir, "chat_history.jsonl.gz")


class ConfigManager:
    """配置管理器兼容类（保持向后兼容）"""
    
    def __init__(self, settings: Settings):
        self._settings = settings
        self.SYSTEM_START_TIME = datetime.now()
    
    @property
    def BASE_DIR(self):
        return self._settings.base_dir
    
    @property
    def DATA_DIR(self):
        return self._settings.data_dir
    
    @property
    def API_KEYS_FILE(self):
        return self._settings.api_keys_file
    
    @property
    def DEVICES_FILE(self):
        return self._settings.devices_file
    
    @property
    def STATS_FILE(self):
        return self._settings.stats_file
    
    @property
    def CHAT_HISTORY_FILE(self):
        return self._settings.chat_history_file
    
    @property
    def MAX_CHAT_HISTORY_SIZE(self):
        return self._settings.max_chat_history_size
    
    @property
    def API_KEYS(self):
        return self._settings.api_keys
    
    @property
    def DEFAULT_URL(self):
        return self._settings.zhipu_api_url
    
    @property
    def DEFAULT_MODEL(self):
        return self._settings.llm_default_model
    
    @property
    def LLM_VERIFY_SSL(self):
        return self._settings.llm_verify_ssl
    
    @property
    def MAX_DEVICES_PER_KEY(self):
        return self._settings.max_devices_per_key
    
    @property
    def APP_PORT(self):
        return self._settings.app_port
    
    def get_base_dir(self) -> str:
        return self.BASE_DIR


settings = Settings()
config = ConfigManager(settings)
