"""
AI Manage Platform - 应用入口
负责 FastAPI 应用装配：CORS、lifespan（连接预热 + 提醒/统计管理器启停）、路由聚合。
所有业务逻辑分散在 app/api/*.py，本文件只做组装。
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings, assert_production_config
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

# 启动自检：检查生产环境关键配置是否齐备（详见 P0-1 修复）
assert_production_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan 事件处理器：启动预热各管理器，关闭时优雅清理"""
    logger.info("正在初始化数据库...")
    from app.models.database import init_db
    init_db()
    logger.info("数据库初始化完成")

    logger.info("正在预热LLM连接...")
    warmup_key = settings.api_keys[0] if settings.api_keys else None
    await llm_infer.warmup(settings.zhipu_api_url, warmup_key)

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
    # 解析 CORS 配置：留空表示允许全部源
    raw_origins = settings.cors_origins.strip()
    if raw_origins:
        app_cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    else:
        app_cors_origins = ["*"]

    # 浏览器规范禁止 allow_origins=["*"] 与 allow_credentials=True 同时存在，
    # 通配源时强制关闭 credentials。
    if "*" in app_cors_origins:
        if settings.cors_credentials:
            logger.warning(
                "CORS allow_origins 为通配 '*'，强制关闭 allow_credentials 以符合浏览器规范。"
                "生产环境请通过 CORS_ORIGINS 配置具体域名。"
            )
        app_cors_credentials = False
    else:
        app_cors_credentials = settings.cors_credentials

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
        allow_origins=app_cors_origins,
        allow_credentials=app_cors_credentials,
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
    from app.api.user_config import router as user_config_router
    from app.api.user_history import router as user_history_router
    from app.api.admin_users import router as admin_users_router
    from app.api.provider_keys import router as provider_keys_router

    app.include_router(auth_router)
    app.include_router(user_config_router)
    app.include_router(user_history_router)
    app.include_router(admin_users_router)
    app.include_router(provider_keys_router)
    app.include_router(chat_router)
    app.include_router(devices_router)
    app.include_router(skills_router)
    app.include_router(reminders_router)
    app.include_router(keys_router)
    app.include_router(stats_router)
    app.include_router(history_router)
    app.include_router(mood_router)
    app.include_router(pages_router)

    # 挂载静态文件服务（必须在 app 实例上 mount，router.mount 不生效）
    from fastapi.staticfiles import StaticFiles
    import os
    _static_dir = os.path.join(settings.base_dir, "app", "static")
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    return app


app = create_app()


def main():
    """启动 uvicorn 服务（带优雅信号处理）"""
    import signal
    import uvicorn

    server_ref = {"instance": None}

    def signal_handler(signum, frame):
        signal_name = "SIGINT(Ctrl+C)" if signum == signal.SIGINT else f"SIGTERM({signum})"
        logger.info("")
        logger.info("=" * 50)
        logger.info("收到信号 %s，正在安全退出...", signal_name)
        logger.info("=" * 50)
        logger.info("  正在关闭连接池...")
        logger.info("  正在保存统计数据...")
        logger.info("  正在释放资源...")
        logger.info("=" * 50)
        if server_ref["instance"]:
            server_ref["instance"].should_exit = True
        else:
            logger.info("  服务已安全退出！")
            logger.info("=" * 50)
            sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if sys.platform == "win32":
        import ctypes
        # Windows 上 Ctrl+C 不会发送 SIGINT，需要用 SetConsoleCtrlHandler 捕获
        WIN_CTRL_C_EVENT = 0
        WIN_CTRL_CLOSE_EVENT = 2

        def win_handler(dwCtrlType, func):
            if dwCtrlType in (WIN_CTRL_C_EVENT, WIN_CTRL_CLOSE_EVENT):
                signal_handler(signal.SIGINT, None)
                return 1
            return 0

        handler_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(handler_type(win_handler), 1)

    config_obj = uvicorn.Config(app, host="0.0.0.0", port=settings.app_port, log_level="info")
    server = uvicorn.Server(config_obj)
    server_ref["instance"] = server
    server.run()


if __name__ == "__main__":
    main()
