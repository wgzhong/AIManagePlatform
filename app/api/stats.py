"""
系统统计与健康检查 API。
"""

from fastapi import APIRouter

from app.core.stats import stats_manager

router = APIRouter()


@router.get("/api/stats")
async def get_stats():
    """获取系统统计数据（全局）"""
    return stats_manager.load_stats()


@router.get("/api/health")
async def health_check():
    """健康检查接口：探测 LLM 服务端连通性"""
    from app.core.llm_infer import llm_infer
    try:
        status = await llm_infer.check_health()
        return {"status": "healthy", **status}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
