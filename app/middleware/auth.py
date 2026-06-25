"""
管理接口鉴权中间件。
通过环境变量 ADMIN_TOKEN 控制开关：
- 未设置 ADMIN_TOKEN：鉴权关闭（仅本地开发推荐，会打印警告）
- 设置了 ADMIN_TOKEN：所有受保护端点要求 Authorization: Bearer <token>
                     或查询参数 ?token=<token>

⚠️ 配置读取统一走 `settings`，禁止直接 `os.environ.get`，
否则在仅写 .env 文件部署时会出现 ADMIN_TOKEN 静默失效事故（详见 P0-1 修复）。
"""

import logging
import secrets
from fastapi import HTTPException, Request, status

from app.core.config import get_effective_admin_token

logger = logging.getLogger("AUTH")

# 启动时读取一次（运行期改环境变量需重启）
# 注意：这里通过 settings 读取，与 .env 文件部署方式一致
ADMIN_TOKEN = get_effective_admin_token()

if not ADMIN_TOKEN:
    logger.warning(
        "⚠️  ADMIN_TOKEN 未设置，管理接口鉴权已关闭！生产环境请务必设置 ADMIN_TOKEN 环境变量。"
    )


def _extract_token(request: Request) -> str:
    """从 Authorization header 或 query 参数提取 token。

    安全提醒：通过 URL query 参数传递 token 存在泄露风险
    （浏览器历史、服务器日志、Referer header），请仅用于 ESP32 等受限场景。
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    # 兼容 query 参数传 token（部分前端/ESP32 场景）
    # 安全警告：query 参数方式会使 token 出现在日志与浏览器历史中
    query_token = request.query_params.get("token", "")
    if query_token:
        logger.warning("通过 query 参数传递 token，存在安全隐患，建议使用 Authorization header")
    return query_token


async def require_admin(request: Request):
    """管理端点依赖：校验 admin token。未配置 token 时直接放行（开发模式）。

    使用 secrets.compare_digest 进行恒定时间比较，防止时序攻击。
    """
    if not ADMIN_TOKEN:
        # 鉴权关闭：开发模式放行
        return True

    token = _extract_token(request)
    if not secrets.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或缺失的管理员令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True
