"""
管理接口鉴权中间件。
通过环境变量 ADMIN_TOKEN 控制开关：
- 未设置 ADMIN_TOKEN：鉴权关闭（仅本地开发推荐，会打印警告）
- 设置了 ADMIN_TOKEN：所有受保护端点要求 Authorization: Bearer <token>
                     或查询参数 ?token=<token>
"""

import os
import logging
from fastapi import HTTPException, Request, status

logger = logging.getLogger("AUTH")

# 启动时读取一次（运行期改环境变量需重启）
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()

if not ADMIN_TOKEN:
    logger.warning(
        "⚠️  ADMIN_TOKEN 未设置，管理接口鉴权已关闭！生产环境请务必设置 ADMIN_TOKEN 环境变量。"
    )


def _extract_token(request: Request) -> str:
    """从 Authorization header 或 query 参数提取 token"""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    # 兼容 query 参数传 token（部分前端/ESP32 场景）
    return request.query_params.get("token", "")


async def require_admin(request: Request):
    """管理端点依赖：校验 admin token。未配置 token 时直接放行（开发模式）。"""
    if not ADMIN_TOKEN:
        # 鉴权关闭：开发模式放行
        return True

    token = _extract_token(request)
    if token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或缺失的管理员令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True
