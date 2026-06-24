"""
聊天历史管理模块（已弃用）
⚠️ 此模块已弃用，聊天历史存储已统一迁移至 SQLite（app/models/database.py）。
保留仅为向后兼容旧版数据，新代码请使用 ChatHistory ORM 模型。
"""
import warnings

import json
import gzip
import logging
import os
from typing import List, Dict, Any

from .config import config

logger = logging.getLogger(__name__)


class ChatHistoryManager:
    """聊天历史管理器类"""
    
    def __init__(self):
        """初始化聊天历史管理器"""
        pass
    
    def load_history(self) -> List[Dict[str, Any]]:
        """从JSON Lines gzip文件加载对话历史"""
        if os.path.exists(config.CHAT_HISTORY_FILE):
            try:
                with gzip.open(config.CHAT_HISTORY_FILE, "rt", encoding="utf-8") as f:
                    history = []
                    for line in f:
                        line = line.strip()
                        if line:
                            history.append(json.loads(line))
                    return history
            except Exception as e:
                logger.warning("加载聊天历史失败: %s", e)
                pass
        return []
    
    def save_history(self, history: List[Dict[str, Any]]) -> None:
        """保存对话历史到JSON Lines gzip文件，超过大小限制时直接裁剪前段"""
        with gzip.open(config.CHAT_HISTORY_FILE, "wt", encoding="utf-8") as f:
            for item in history:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        file_size = os.path.getsize(config.CHAT_HISTORY_FILE)
        if file_size > config.MAX_CHAT_HISTORY_SIZE and len(history) > 1:
            # 估算每条平均大小，一次性裁剪到安全范围
            avg_size = file_size / len(history)
            keep_count = max(1, int(config.MAX_CHAT_HISTORY_SIZE / avg_size * 0.8))
            trimmed = history[-keep_count:]
            with gzip.open(config.CHAT_HISTORY_FILE, "wt", encoding="utf-8") as f:
                for item in trimmed:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            logger.info("聊天历史裁剪: %d 条 -> %d 条", len(history), len(trimmed))


chat_history_manager = ChatHistoryManager()
