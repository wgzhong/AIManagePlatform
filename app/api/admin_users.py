"""
管理员用户管理 API：用户列表、单个用户查看/更新/删除、查看所有用户配置。
（拆分自原 auth.py，第三阶段 F1/F3 重构）

所有端点均要求超级管理员权限（通过 require_superuser 依赖）。
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import EmailStr

from app.models.database import get_db
from app.core.redact import mask_api_key
from app.services.user_service import (
    get_all_users, get_user_by_id, delete_user, update_user,
    get_user_config,
)
from app.api.auth_deps import get_current_user, require_superuser
from app.schemas.admin import (
    UserListItem, UserListResponse, UserUpdateResponse,
    UserConfigItem, AllUserConfigsResponse,
)
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/auth", tags=["admin-users"])


@router.get("/users", response_model=List[UserListItem])
def get_users(
    current_user=Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """管理员获取所有用户列表（含贡献技能数量）"""
    from app.models.database import UserSkill

    users = get_all_users(db)
    result = []
    for user in users:
        # 统计该用户的贡献技能数
        contrib_count = db.query(UserSkill).filter(
            UserSkill.user_id == user.id,
            UserSkill.is_contributed == True,
        ).count()
        result.append(
            UserListItem(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at.isoformat() if user.created_at else "",
                contributed_skills_count=contrib_count,
            )
        )
    return result


@router.get("/users/{user_id}", response_model=UserListItem)
def get_single_user(
    user_id: int,
    current_user=Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """管理员获取单个用户"""
    from app.models.database import UserSkill

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    contrib_count = db.query(UserSkill).filter(
        UserSkill.user_id == user_id,
        UserSkill.is_contributed == True,
    ).count()

    return UserListItem(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at.isoformat() if user.created_at else "",
        contributed_skills_count=contrib_count,
    )


@router.put("/users/{user_id}", response_model=UserUpdateResponse)
def update_single_user(
    user_id: int,
    username: str = None,
    email: EmailStr = None,
    is_active: bool = None,
    is_superuser: bool = None,
    current_user=Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """管理员更新用户信息"""
    updates = {}
    if username is not None:
        updates["username"] = username
    if email is not None:
        updates["email"] = email
    if is_active is not None:
        updates["is_active"] = is_active
    if is_superuser is not None:
        updates["is_superuser"] = is_superuser

    user = update_user(db, user_id, **updates)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return UserUpdateResponse(
        message="用户信息更新成功",
        user=UserListItem(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at.isoformat() if user.created_at else "",
        ),
    )


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_single_user(
    user_id: int,
    current_user=Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """管理员删除用户"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    success = delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")

    return MessageResponse(message="用户删除成功")


@router.get("/admin/user-configs", response_model=List[UserConfigItem])
def get_all_user_configs(
    current_user=Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """超级管理员查看所有用户的配置

    ⚠️ 安全：API Key 必须脱敏返回，避免管理员一次请求即泄露全部用户的智谱 Key。
    """
    users = get_all_users(db)
    configs = []
    for user in users:
        config = get_user_config(db, user.id)
        configs.append(
            UserConfigItem(
                user_id=user.id,
                username=user.username,
                email=user.email,
                is_superuser=user.is_superuser,
                api_key=mask_api_key(config.api_key) if config else "",
                api_url=config.api_url if config else "",
                default_model=config.default_model if config else "",
                mood=config.mood if config else "",
                custom_models=config.custom_models if config else [],
            )
        )
    return configs
