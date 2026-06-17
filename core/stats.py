"""
统计管理模块
负责管理系统统计数据的存储和查询
"""

import json
import os
import threading
from datetime import datetime
from typing import Dict, Any

from .config import config


class StatsManager:
    """统计管理器类"""
    
    def __init__(self):
        """初始化统计管理器"""
        self._lock = threading.Lock()
    
    def load_stats(self) -> Dict[str, Any]:
        """从文件加载统计数据"""
        if os.path.exists(config.STATS_FILE):
            try:
                with open(config.STATS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        
        return {
            "daily_requests": 0,
            "total_requests": 0,
            "today_output_tokens": 0,
            "total_output_tokens": 0,
            "tool_calls": {"get_time": 0, "calculate": 0, "read_file": 0, "total": 0},
            "daily_records": [],
            "last_reset": datetime.now().isoformat()
        }
    
    def save_stats(self, stats: Dict[str, Any]) -> None:
        """保存统计数据到文件"""
        with open(config.STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    
    def increment_request_count(self) -> None:
        """增加请求计数"""
        with self._lock:
            stats = self.load_stats()
            today = datetime.now().date().isoformat()
            
            if not stats.get("last_reset") or stats["last_reset"] != today:
                stats["daily_requests"] = 0
                stats["today_output_tokens"] = 0
                stats["last_reset"] = today
            
            stats["daily_requests"] += 1
            stats["total_requests"] += 1
            
            found = False
            for record in stats["daily_records"]:
                if record["date"] == today:
                    record["count"] += 1
                    found = True
                    break
            if not found:
                stats["daily_records"].append({"date": today, "count": 1})
            
            self.save_stats(stats)
    
    def update_token_usage(self, output_tokens: int) -> None:
        """更新Token使用统计（只统计输出token）"""
        with self._lock:
            stats = self.load_stats()
            today = datetime.now().date().isoformat()
            
            if stats.get("last_reset") != today:
                stats["today_output_tokens"] = 0
                stats["last_reset"] = today
            
            stats["today_output_tokens"] += output_tokens
            stats["total_output_tokens"] += output_tokens
            self.save_stats(stats)
    
    def increment_tool_call(self, tool_name: str) -> None:
        """增加工具调用计数"""
        with self._lock:
            stats = self.load_stats()
            
            if tool_name in stats["tool_calls"]:
                stats["tool_calls"][tool_name] += 1
            stats["tool_calls"]["total"] += 1
            
            self.save_stats(stats)


stats_manager = StatsManager()
