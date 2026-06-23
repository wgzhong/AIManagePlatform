"""
心情提示相关的请求/响应模型
"""

from pydantic import BaseModel


class MoodPromptResponse(BaseModel):
    """心情提示响应模型"""
    mood: str
    prompt: str
