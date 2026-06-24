"""
用户认证API路由
提供注册、登录、获取用户信息等接口
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.models.database import get_db
from app.services.user_service import (
    create_user, authenticate_user, create_access_token,
    get_user_by_email, get_user_by_username, get_user_by_id, get_user_config,
    update_user_config, get_chat_history, delete_chat_history,
    get_all_users, delete_user, update_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class UserCreate(BaseModel):
    """用户注册请求模型"""
    username: str
    email: EmailStr
    password: str


class TokenData(BaseModel):
    """Token数据模型"""
    email: str | None = None


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """获取当前登录用户"""
    from jose import JWTError, jwt
    from app.services.user_service import SECRET_KEY, ALGORITHM
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


@router.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    if get_user_by_email(db, user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    if get_user_by_username(db, user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被使用"
        )
    
    new_user = create_user(db, user.username, user.email, user.password)
    return {
        "id": int(new_user.id),
        "username": str(new_user.username),
        "email": str(new_user.email),
        "is_active": bool(new_user.is_active),
        "created_at": new_user.created_at.isoformat() if new_user.created_at else ""
    }


@router.post("/login")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """用户登录"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": int(user.id),
            "username": str(user.username),
            "email": str(user.email),
            "is_active": bool(user.is_active),
            "is_superuser": bool(user.is_superuser),
            "created_at": user.created_at.isoformat() if user.created_at else ""
        }
    }


@router.get("/me")
async def read_users_me(current_user = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": int(current_user.id),
        "username": str(current_user.username),
        "email": str(current_user.email),
        "is_active": bool(current_user.is_active),
        "is_superuser": bool(current_user.is_superuser),
        "created_at": current_user.created_at.isoformat() if current_user.created_at else ""
    }


@router.get("/config")
async def get_config(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户配置"""
    config = get_user_config(db, current_user.id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    return {
        "api_key": config.api_key,
        "api_url": config.api_url,
        "default_model": config.default_model,
        "mood": config.mood,
        "custom_models": config.custom_models,
        "settings": config.settings,
        "skills": config.skills
    }


@router.put("/config")
async def update_config(
    api_key: str = None,
    api_url: str = None,
    default_model: str = None,
    mood: str = None,
    custom_models: list = None,
    settings: dict = None,
    skills: list = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户配置"""
    updates = {}
    if api_key is not None:
        updates["api_key"] = api_key
    if api_url is not None:
        updates["api_url"] = api_url
    if default_model is not None:
        updates["default_model"] = default_model
    if mood is not None:
        updates["mood"] = mood
    if custom_models is not None:
        updates["custom_models"] = custom_models
    if settings is not None:
        updates["settings"] = settings
    if skills is not None:
        updates["skills"] = skills
    
    config = update_user_config(db, current_user.id, **updates)
    
    return {
        "message": "配置更新成功",
        "config": {
            "api_key": config.api_key,
            "api_url": config.api_url,
            "default_model": config.default_model,
            "mood": config.mood,
            "custom_models": config.custom_models,
            "settings": config.settings,
            "skills": config.skills
        }
    }


@router.get("/history")
async def get_history(limit: int = 100, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户聊天记录"""
    histories = get_chat_history(db, current_user.id, limit)
    return [{
        "role": h.role,
        "content": h.content,
        "model": h.model,
        "created_at": h.created_at.isoformat()
    } for h in histories]


@router.delete("/history")
async def clear_history(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """清空用户聊天记录"""
    delete_chat_history(db, current_user.id)
    return {"message": "聊天记录已清空"}


@router.post("/logout")
async def logout():
    """用户登出"""
    return {"message": "登出成功"}


@router.get("/stats")
async def get_user_stats(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户的统计数据（含全局设备信息）"""
    from app.services.stats_service import get_user_stats_dict
    from app.core.devices import device_manager
    
    stats = get_user_stats_dict(db, current_user.id)
    
    # 添加全局设备统计
    try:
        all_devices = device_manager.get_all_devices()
        stats["online_devices"] = 0  # 当前无在线状态跟踪
        stats["total_devices"] = len(all_devices)
    except Exception:
        stats["online_devices"] = 0
        stats["total_devices"] = 0
    
    return stats


@router.get("/users")
async def get_users(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """管理员获取所有用户列表"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此接口"
        )
    
    users = get_all_users(db)
    return [{
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at.isoformat() if user.created_at else ""
    } for user in users]


@router.get("/users/{user_id}")
async def get_single_user(user_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """管理员获取单个用户"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此接口"
        )
    
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at.isoformat() if user.created_at else ""
    }


@router.put("/users/{user_id}")
async def update_single_user(
    user_id: int,
    username: str = None,
    email: EmailStr = None,
    is_active: bool = None,
    is_superuser: bool = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理员更新用户信息"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此接口"
        )
    
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
    
    return {
        "message": "用户信息更新成功",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        }
    }


@router.delete("/users/{user_id}")
async def delete_single_user(user_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """管理员删除用户"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此接口"
        )
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    success = delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return {"message": "用户删除成功"}


# ── 管理员查看用户配置 ──

@router.get("/admin/user-configs")
async def get_all_user_configs(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """超级管理员查看所有用户的配置"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此接口"
        )
    
    users = get_all_users(db)
    configs = []
    for user in users:
        config = get_user_config(db, user.id)
        configs.append({
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "is_superuser": user.is_superuser,
            "api_key": config.api_key if config else "",
            "api_url": config.api_url if config else "",
            "default_model": config.default_model if config else "",
            "mood": config.mood if config else "",
            "custom_models": config.custom_models if config else [],
        })
    return configs
