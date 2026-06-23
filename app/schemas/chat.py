"""
聊天相关的请求/响应模型
"""

from typing import List, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """聊天请求模型"""
    messages: List[dict]
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    model: str = "glm-5.1"
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.7
    top_k: int = 50
    frequency_penalty: float = 0.5
    enable_think: bool = False
    device_code: Optional[str] = None
    enabled_tools: Optional[List[str]] = None
    mood: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应模型"""
    content: Optional[str] = None
    tool_result: Optional[dict] = None
    usage: Optional[dict] = None
    error: Optional[str] = None
