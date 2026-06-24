"""
AI Manage Platform - 应用入口
负责 FastAPI 应用装配：CORS、lifespan（连接预热 + 提醒/统计管理器启停）、路由聚合。
所有业务逻辑分散在 app/api/*.py，本文件只做组装。
"""

import logging
import os
import sys
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import config, settings
from app.core.logging import setup_logging
from app.core.exception import register_exception_handlers
from app.core.reminder_manager import reminder_manager
from app.core.stats import stats_manager
from app.core.llm_infer import llm_infer
from app.middleware.rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

setup_logging(log_level=settings.llm_debug and "DEBUG" or "INFO")
logger = logging.getLogger("APP")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan 事件处理器：启动预热各管理器，关闭时优雅清理"""
    logger.info("正在初始化数据库...")
    from app.models.database import init_db
    init_db()
    logger.info("数据库初始化完成")

    logger.info("正在预热LLM连接...")
    warmup_key = config.API_KEYS[0] if config.API_KEYS else None
    await llm_infer.warmup(config.DEFAULT_URL, warmup_key)

    logger.info("正在启动提醒管理器...")
    reminder_manager.start()
    logger.info(
        "提醒管理器启动完成，待执行提醒数: %d", len(reminder_manager.get_pending_reminders())
    )

    logger.info("正在启动统计落盘线程...")
    stats_manager.start()

    yield

    logger.info("正在关闭应用...")
    stats_manager.stop()
    reminder_manager.stop()
    await llm_infer.close()
    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例"""
    app = FastAPI(
        title="AI Manage Platform",
        description="""
AI 推理对话平台 API 文档

**核心功能：**
- SSE 流式对话：对接智谱 GLM 系列模型，支持工具调用
- 设备管理：ESP32 设备注册、设备码验证、使用统计
- 技能系统：插件化设计，支持 Python 类和 md 文件技能定义
- 定时提醒：APScheduler 定时任务 + SSE 实时推送通知
- 情绪响应：7种情绪状态（开心/生气/难过/害怕/厌恶/惊讶/愉快）
- 统计分析：请求量、Token 消耗、工具调用统计

**API 鉴权：**
- 管理接口：需要 Admin Token（请求头 X-Admin-Token）
- 聊天接口：支持 API Key 或设备码验证
""",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    register_exception_handlers(app)

    from app.api.chat import router as chat_router
    from app.api.devices import router as devices_router
    from app.api.skills import router as skills_router
    from app.api.reminders import router as reminders_router
    from app.api.keys import router as keys_router
    from app.api.stats import router as stats_router
    from app.api.history import router as history_router
    from app.api.mood import router as mood_router
    from app.api.pages import router as pages_router
    from app.api.auth import router as auth_router

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(devices_router)
    app.include_router(skills_router)
    app.include_router(reminders_router)
    app.include_router(keys_router)
    app.include_router(stats_router)
    app.include_router(history_router)
    app.include_router(mood_router)
    app.include_router(pages_router)

    return app


app = create_app()


def main():
    """启动 uvicorn 服务（带优雅信号处理）"""
    import signal
    import uvicorn

    server_ref = {"instance": None}

    def signal_handler(signum, frame):
        logger.info("收到信号 %s，正在优雅关闭...", signum)
        if server_ref["instance"]:
            server_ref["instance"].should_exit = True
        else:
            sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if sys.platform == "win32":
        import ctypes
        
        def handler(dwCtrlType, func):
            if dwCtrlType in [0, 2]:
                signal_handler(signal.SIGINT, None)
                return 1
            return 0
        
        ctypes.windll.kernel32.SetConsoleCtrlHandler(ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)(handler), 1)

    config_obj = uvicorn.Config(app, host="0.0.0.0", port=config.APP_PORT, log_level="info")
    server = uvicorn.Server(config_obj)
    server_ref["instance"] = server
    server.run()


if __name__ == "__main__":
    main()
