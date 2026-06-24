"""
静态页面路由：首页、聊天、设备、技能配置页。
"""

import os

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import config

router = APIRouter()

STATIC_DIR = os.path.join(config.BASE_DIR, "app", "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# 挂载静态资源目录（/static 前缀）
router.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@router.get("/")
async def index():
    """首页"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/home")
async def home_page():
    """主页面"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/login")
async def login_page():
    """登录页面"""
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@router.get("/chat")
async def chat_page():
    """聊天页面"""
    return FileResponse(os.path.join(STATIC_DIR, "chat.html"))


@router.get("/devices")
async def devices_page():
    """设备管理页面"""
    return FileResponse(os.path.join(STATIC_DIR, "devices.html"))


@router.get("/skills")
async def skills_page():
    """Skills 配置页面"""
    return FileResponse(os.path.join(STATIC_DIR, "skills.html"))
