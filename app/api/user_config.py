"""
用户配置 API：获取/更新当前用户的 API Key、模型、情绪等配置。
（拆分自原 auth.py，第三阶段 F1/F3 重构）

安全说明：GET 接口返回的 api_key 一律脱敏，避免 XSS 或日志泄露。
写入完整 API Key 请走 PUT /auth/config。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.core.redact import mask_api_key
from app.services.user_service import get_user_config, update_user_config
from app.api.auth_deps import get_current_user
from app.schemas.user import (
    UserConfigResponse, UserConfigUpdate, UserConfigUpdateResponse,
)

router = APIRouter(prefix="/auth", tags=["user-config"])


@router.get("/config", response_model=UserConfigResponse)
def get_config(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户配置（API Key 脱敏返回）"""
    config = get_user_config(db, current_user.id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    return UserConfigResponse(
        api_key=mask_api_key(config.api_key),
        api_url=config.api_url or "",
        default_model=config.default_model or "",
        mood=config.mood or "",
        custom_models=config.custom_models or [],
        settings=config.settings or {},
        skills=config.skills or [],
    )


@router.put("/config", response_model=UserConfigUpdateResponse)
def update_config(
    body: UserConfigUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新用户配置（JSON body）"""
    updates = {}
    for field in ("api_key", "api_url", "default_model", "mood", "custom_models", "settings", "skills"):
        val = getattr(body, field, None)
        if val is not None:
            updates[field] = val

    config = update_user_config(db, current_user.id, **updates)

    return UserConfigUpdateResponse(
        message="配置更新成功",
        config=UserConfigResponse(
            api_key=mask_api_key(config.api_key),
            api_url=config.api_url or "",
            default_model=config.default_model or "",
            mood=config.mood or "",
            custom_models=config.custom_models or [],
            settings=config.settings or {},
            skills=config.skills or [],
        ),
    )
