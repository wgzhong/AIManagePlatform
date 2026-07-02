"""
用户认证 API：注册、登录、获取当前用户、登出、刷新令牌。
（拆分自原 auth.py，第三阶段 F2/F3 重构）

JWT 双令牌机制：
- access_token  短期（30 分钟），用于 API 鉴权
- refresh_token 长期（7 天），仅用于 /auth/refresh 换取新 access_token
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.models.database import get_db
from app.services.user_service import (
    create_user, authenticate_user,
    create_access_token, create_refresh_token,
    verify_refresh_token, get_user_by_email, get_user_by_username,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.api.auth_deps import get_current_user
from app.schemas.auth import (
    UserCreate, RegisterResponse, TokenResponse, UserPublic,
    RefreshTokenRequest, RefreshTokenResponse, MessageResponse,
)
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
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
    return RegisterResponse(
        id=int(new_user.id),
        username=str(new_user.username),
        email=str(new_user.email),
        is_active=bool(new_user.is_active),
        created_at=new_user.created_at.isoformat() if new_user.created_at else "",
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """用户登录，返回 access_token + refresh_token"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": user.email}, expires_delta=refresh_expires
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserPublic(
            id=int(user.id),
            username=str(user.username),
            email=str(user.email),
            is_active=bool(user.is_active),
            is_superuser=bool(user.is_superuser),
            created_at=user.created_at.isoformat() if user.created_at else "",
        ),
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_access_token(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    """用 refresh_token 换取新的 access_token。

    refresh_token 本身依然有效（不轮换），仅签发新的 access_token。
    """
    email = verify_refresh_token(body.refresh_token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh_token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_email(db, email=email)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_expires
    )

    return RefreshTokenResponse(
        access_token=new_access_token,
        token_type="bearer",
    )


@router.get("/me", response_model=UserPublic)
def read_users_me(current_user=Depends(get_current_user)):
    """获取当前用户信息"""
    return UserPublic(
        id=int(current_user.id),
        username=str(current_user.username),
        email=str(current_user.email),
        is_active=bool(current_user.is_active),
        is_superuser=bool(current_user.is_superuser),
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request):
    """用户登出，将 token 加入黑名单使其立即失效"""
    from app.core.jwt_blacklist import add_to_blacklist
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供 token")
    token = auth_header[7:]  # 去掉 "Bearer " 前缀
    
    add_to_blacklist(token)
    from app.core.jwt_blacklist import cleanup_expired
    cleanup_expired()  # 每次 logout 时顺带清理过期 token
    return MessageResponse(message="登出成功")
