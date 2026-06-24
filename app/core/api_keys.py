"""
API Key管理模块
负责管理API Key的生成、存储和验证。
存储于磁盘时使用 Fernet 加密保护（需配置 ENCRYPTION_KEY 环境变量）。
"""

import json
import logging
import os
import secrets
from typing import List, Optional

from .config import config
from .crypto import encrypt, decrypt

logger = logging.getLogger(__name__)


class APIKeyManager:
    """API Key管理器类"""
    
    def __init__(self):
        """初始化API Key管理器"""
        pass
    
    def load_keys(self) -> List[str]:
        """从文件加载并解密API Key列表"""
        if os.path.exists(config.API_KEYS_FILE):
            try:
                with open(config.API_KEYS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_keys = data.get("keys", [])
                    return [decrypt(k) for k in raw_keys]
            except Exception as e:
                logger.warning("加载 API Keys 失败: %s", e)
        return config.API_KEYS
    
    def save_keys(self, keys: List[str]) -> None:
        """加密并保存API Key列表到文件"""
        encrypted_keys = [encrypt(k) for k in keys]
        with open(config.API_KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump({"keys": encrypted_keys}, f, ensure_ascii=False, indent=2)
    
    def generate_key(self) -> str:
        """生成一个新的随机API Key"""
        return secrets.token_urlsafe(32)
    
    def add_key(self, key: str) -> None:
        """添加一个新的API Key"""
        keys = self.load_keys()
        if key not in keys:
            keys.append(key)
            self.save_keys(keys)
    
    def remove_key(self, key: str) -> bool:
        """删除一个API Key，返回是否成功"""
        keys = self.load_keys()
        if key in keys:
            keys.remove(key)
            self.save_keys(keys)
            return True
        return False
    
    def validate_key(self, key: str) -> bool:
        """验证API Key是否有效"""
        keys = self.load_keys()
        return key in keys


api_key_manager = APIKeyManager()
