"""
LLM 健康检查模块。

职责：向 LLM 服务端发轻量请求探测连通性，返回结构化健康状态。

从原 llm_infer.py 拆分（详见第三阶段 F4 重构）。
"""

import logging
import time
from typing import Dict

from .llm_client import llm_client
from .config import settings

logger = logging.getLogger("LLM")


async def check_health() -> Dict:
    """健康检查：向 LLM 服务端发一个轻量请求探测连通性。

    Returns:
        {"healthy": bool, "status_code": int|None, "detail": str, "latency_ms": float|None}
    """
    start = time.time()
    if not settings.api_keys:
        return {"healthy": False, "status_code": None, "detail": "未配置 API Key"}

    client = llm_client.get_client()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.api_keys[0]}",
    }
    payload = llm_client.fast_json_dumps({
        "model": settings.llm_default_model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    })
    try:
        response = await client.post(
            settings.zhipu_api_url,
            content=payload,
            headers=headers,
            timeout=10.0,
        )
        elapsed = (time.time() - start) * 1000
        # 智谱返回 200 表示连通正常；4xx 通常是鉴权/参数，但说明网络通
        healthy = response.status_code < 500
        return {
            "healthy": healthy,
            "status_code": response.status_code,
            "latency_ms": round(elapsed, 2),
            "detail": "ok" if healthy else response.text[:120],
        }
    except Exception as e:
        return {
            "healthy": False,
            "status_code": None,
            "detail": f"{type(e).__name__}: {str(e)[:120]}",
        }
