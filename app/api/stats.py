"""
系统统计与健康检查 API。
（第三阶段 F3 重构：补 response_model）

注意：
- /api/stats 走同步 DB 读取，改为 def（FastAPI 自动放线程池）
- /api/health 内部 await llm 健康检查，必须保持 async
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.stats import stats_manager
from app.middleware.auth import require_admin

router = APIRouter()


class StatsResponse(BaseModel):
    """统计响应（字段不固定，用 dict 兜底）"""
    # 实际返回字段由 stats_manager.load_stats() 决定，这里仅作 OpenAPI 提示
    pass


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    healthy: bool = False
    status_code: int | None = None
    latency_ms: float | None = None
    detail: str = ""


@router.get("/api/stats")
def get_stats(_: bool = Depends(require_admin)):
    """获取系统统计数据（全局，需 admin 鉴权）"""
    return stats_manager.load_stats()


@router.get("/api/health", response_model=HealthResponse)
async def health_check(_: bool = Depends(require_admin)):
    """健康检查接口：探测 LLM 服务端连通性

    ⚠️ 需 admin 鉴权，防止被滥用做 SSRF 或耗 LLM 配额（详见 S8 修复）。
    """
    from app.core.llm_health import check_health
    try:
        result = await check_health()
        if result.get("healthy"):
            return HealthResponse(
                status="healthy",
                healthy=True,
                status_code=result.get("status_code"),
                latency_ms=result.get("latency_ms"),
                detail="ok",
            )
        return HealthResponse(
            status="unhealthy",
            healthy=False,
            status_code=result.get("status_code"),
            latency_ms=result.get("latency_ms"),
            detail=result.get("detail", ""),
        )
    except Exception as e:
        return HealthResponse(status="unhealthy", detail=str(e))
