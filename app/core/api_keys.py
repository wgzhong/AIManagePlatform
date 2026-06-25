"""
API Key管理模块
负责管理API Key的生成、存储和验证。
存储于磁盘时使用 Fernet 加密保护（需配置 ENCRYPTION_KEY 环境变量）。
"""

import hmac
import json
import logging
import os
import secrets
from typing import List, Optional

from .config import settings
from .crypto import encrypt, decrypt

logger = logging.getLogger(__name__)


class APIKeyManager:
    """API Key管理器类"""

    def __init__(self):
        """初始化API Key管理器"""
        pass

    def load_keys(self) -> List[str]:
        """从文件加载并解密API Key列表"""
        if os.path.exists(settings.api_keys_file):
            try:
                with open(settings.api_keys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_keys = data.get("keys", [])
                    return [decrypt(k) for k in raw_keys]
            except Exception as e:
                logger.warning("加载 API Keys 失败: %s", e)
        return settings.api_keys

    def save_keys(self, keys: List[str]) -> None:
        """加密并保存API Key列表到文件"""
        encrypted_keys = [encrypt(k) for k in keys]
        with open(settings.api_keys_file, "w", encoding="utf-8") as f:
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
        """验证API Key是否有效

        ⚠️ 使用 hmac.compare_digest 进行恒定时间比较，防止时序攻击（详见 S5 修复）。
        """
        if not key:
            return False
        keys = self.load_keys()
        # 逐个比较：每个 compare_digest 都是常量时间，整体循环仍是 O(n)，
        # 但攻击者无法从单次比较耗时推断正确字符数，安全性已足够。
        for stored in keys:
            if hmac.compare_digest(stored, key):
                return True
        return False


api_key_manager = APIKeyManager()
