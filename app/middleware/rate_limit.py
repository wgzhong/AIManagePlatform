"""
/chat 端点限流中间件（基于 slowapi）。
按设备码或客户端 IP 限流，防止单个客户端打爆 LLM API 配额。

限流策略通过环境变量 CHAT_RATE_LIMIT 配置（格式 "次数/周期"，如 "30/minute"），
默认 30/minute。
"""

import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# 限流策略：默认每分钟 30 次
RATE_LIMIT = os.environ.get("CHAT_RATE_LIMIT", "30/minute")


def _get_chat_key(request) -> str:
    """
    限流键：优先用请求体里的 device_code（硬件设备维度），
    其次用客户端 IP。在端点内通过装饰器无法拿到 body，
    这里统一退化为 IP 维度（足以防止单 IP 滥用）。
    """
    return get_remote_address(request)


# limiter 实例：用自定义 key_func，按 IP 限流
limiter = Limiter(key_func=get_remote_address)


def apply_chat_limit(handler):
    """对 /chat 处理函数应用限流装饰器"""
    return limiter.limit(RATE_LIMIT)(handler)
