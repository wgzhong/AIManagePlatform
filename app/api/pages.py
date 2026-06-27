"""
静态页面路由：首页、聊天、设备、技能配置页。
"""

import os

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

router = APIRouter()

STATIC_DIR = os.path.join(settings.base_dir, "app", "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# 静态资源挂载已移至 app/main.py 的 create_app() 中（必须用 app.mount 而非 router.mount）


@router.get("/")
def index():
    """首页"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/home")
def home_page():
    """主页面"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/login")
def login_page():
    """登录页面"""
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@router.get("/chat")
def chat_page():
    """聊天页面"""
    return FileResponse(os.path.join(STATIC_DIR, "chat.html"))


@router.get("/devices")
def devices_page():
    """设备管理页面"""
    return FileResponse(os.path.join(STATIC_DIR, "devices.html"))


@router.get("/skills")
def skills_page():
    """Skills 配置页面（禁用缓存，确保用户始终获取最新版本）"""
    return FileResponse(
        os.path.join(STATIC_DIR, "skills.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/apikeys")
def apikeys_page():
    """API Key 管理中心页面"""
    return FileResponse(
        os.path.join(STATIC_DIR, "apikeys.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
