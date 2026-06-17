"""
配置管理模块
负责管理应用的配置参数和文件路径
"""

import os
from datetime import datetime


class ConfigManager:
    """配置管理器类"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.DATA_DIR = os.path.join(self.BASE_DIR, "data")
        os.makedirs(self.DATA_DIR, exist_ok=True)
        
        self.API_KEYS_FILE = os.path.join(self.DATA_DIR, "api_keys.json")
        self.DEVICES_FILE = os.path.join(self.DATA_DIR, "devices.json")
        self.STATS_FILE = os.path.join(self.DATA_DIR, "stats.json")
        self.CHAT_HISTORY_FILE = os.path.join(self.DATA_DIR, "chat_history.jsonl.gz")
        
        self.MAX_CHAT_HISTORY_SIZE = 10 * 1024 * 1024
        self.API_KEYS = ["your_api_key_1"]
        self.DEFAULT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.MAX_USERS_PER_KEY = 50
        self.SYSTEM_START_TIME = datetime.now()
    
    def get_base_dir(self) -> str:
        """获取项目基础目录"""
        return self.BASE_DIR


config = ConfigManager()
