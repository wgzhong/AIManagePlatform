"""
聊天历史管理模块
负责对话历史的存储和查询
支持JSON Lines格式和gzip压缩
"""

import json
import gzip
import os
from typing import List, Dict, Any

from .config import config


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
            except Exception:
                pass
        return []
    
    def save_history(self, history: List[Dict[str, Any]]) -> None:
        """保存对话历史到JSON Lines gzip文件，超过10M自动清理旧记录"""
        with gzip.open(config.CHAT_HISTORY_FILE, "wt", encoding="utf-8") as f:
            for item in history:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        file_size = os.path.getsize(config.CHAT_HISTORY_FILE)
        if file_size > config.MAX_CHAT_HISTORY_SIZE:
            while file_size > config.MAX_CHAT_HISTORY_SIZE and len(history) > 1:
                history.pop(0)
                with gzip.open(config.CHAT_HISTORY_FILE, "wt", encoding="utf-8") as f:
                    for item in history:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                file_size = os.path.getsize(config.CHAT_HISTORY_FILE)


chat_history_manager = ChatHistoryManager()
