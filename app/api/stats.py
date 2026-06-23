"""
系统统计与健康检查 API。
使用 StatsService 封装业务逻辑。
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.schemas.stats import StatsResponse, HealthResponse
from app.services.stats_service import StatsService

router = APIRouter()


def get_stats_service() -> StatsService:
    return StatsService()


@router.get("/api/stats", response_model=StatsResponse)
async def get_stats(service: StatsService = Depends(get_stats_service)):
    """获取系统统计数据"""
    return service.get_stats()


@router.get("/api/health", response_model=HealthResponse)
async def health_check(service: StatsService = Depends(get_stats_service)):
    """健康检查接口：探测 LLM 服务端连通性"""
    return await service.check_health()
