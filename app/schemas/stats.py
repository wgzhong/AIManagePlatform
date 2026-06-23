"""
系统统计相关的请求/响应模型
"""

from typing import Optional
from pydantic import BaseModel


class StatsResponse(BaseModel):
    """系统统计响应模型"""
    daily_requests: int
    total_requests: int
    growth_rate: float
    online_devices: int
    total_devices: int
    today_output_tokens: int
    total_output_tokens: int
    tool_calls: dict
    daily_records: list
    uptime: str
    version: str
    skill_version: str


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str
    status_color: str
    latency: Optional[float]
    timestamp: str
