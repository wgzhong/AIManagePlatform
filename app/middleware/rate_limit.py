"""
/chat 端点限流中间件（基于 slowapi）。
按客户端 IP 限流，防止单个客户端打爆 LLM API 配额。

限流策略通过配置项 CHAT_RATE_LIMIT 配置（格式 "次数/周期"，如 "30/minute"），
默认 30/minute。

⚠️ 配置统一走 settings，不直接读 os.environ（详见 P0-1 修复）。
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# 限流策略：默认每分钟 30 次
RATE_LIMIT = settings.chat_rate_limit or "30/minute"

# limiter 实例：按 IP 限流
limiter = Limiter(key_func=get_remote_address)
