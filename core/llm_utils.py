"""
LLM工具调用工具模块
负责处理工具匹配、工具调用决策等功能
"""

import json
import re
from typing import List, Dict, Optional, Any


class LLMUtils:
    """LLM工具调用工具类"""
    
    @staticmethod
    def quick_tool_match(message: str, enabled_tools: Optional[List[str]] = None) -> Optional[Dict]:
        """快速匹配工具调用"""
        if enabled_tools is None:
            enabled_tools = ["get_time", "calculate", "read_file"]
        
        if "几点" in message or "时间" in message or "日期" in message:
            if "get_time" in enabled_tools:
                return {"tool_name": "get_time", "arguments": {}}
        
        if "计算" in message or "等于" in message or "+" in message or "-" in message or "*" in message or "/" in message:
            if "calculate" in enabled_tools:
                match = re.search(r"[\d+\-*/().\s]+", message)
                if match:
                    return {"tool_name": "calculate", "arguments": {"expression": match.group().strip()}}
        
        return None
    
    @staticmethod
    def is_chitchat(message: str) -> bool:
        """判断是否为闲聊"""
        chitchat_keywords = ["你好", "你是谁", "叫什么", "聊聊天", "在吗", "好的", "谢谢", "不客气", "再见", "拜拜"]
        for keyword in chitchat_keywords:
            if keyword in message:
                return True
        return False
    
    @staticmethod
    def build_tool_system_prompt(tools: List[Dict]) -> str:
        """构建工具调用的系统提示词"""
        prompt = "你可以使用以下工具来帮助回答问题：\n\n"
        
        for tool in tools:
            prompt += f"- {tool['name']}: {tool['description']}\n"
            if tool.get("parameters"):
                params = []
                for param in tool["parameters"]:
                    params.append(f"{param['name']} ({param.get('type', 'string')}): {param['description']}")
                prompt += f"  参数: {', '.join(params)}\n"
            prompt += "\n"
        
        prompt += "当你决定调用工具时，请使用以下格式：\n"
        prompt += "<function name=\"工具名\">参数内容</function>\n\n"
        prompt += "请确保参数格式正确，如果不需要调用工具，可以直接回答问题。"
        
        return prompt
    
    @staticmethod
    def parse_json_tool_call(text: str) -> Optional[Dict[str, Any]]:
        """解析JSON格式的工具调用"""
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        
        match = re.search(r"<function name=\"(\w+)\">(.*?)</function>", text)
        if match:
            return {
                "name": match.group(1),
                "arguments": {"content": match.group(2).strip()}
            }
        
        return None
    
    @staticmethod
    def is_tool_call_decision(decision: Optional[Dict]) -> bool:
        """判断是否为工具调用决策"""
        if decision is None:
            return False
        if "tool_name" in decision or "name" in decision:
            return True
        return False


llm_utils