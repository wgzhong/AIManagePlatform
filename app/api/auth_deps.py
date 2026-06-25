"""
认证相关共享依赖。
把 JWT 解析逻辑从 auth.py 路由层抽离，供所有需要当前用户的路由复用。
（详见第二阶段 A6/F7 重构）
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.database import get_db
from app.services.user_service import get_user_by_email

# OAuth2 tokenUrl 指向登录端点，用于 OpenAPI 文档的"Authorize"按钮
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class TokenData(BaseModel):
    """Token 数据模型"""
    email: str | None = None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """解析 JWT 并返回当前用户对象。

    作为 FastAPI 依赖使用：
        @router.get("/me")
        async def me(current_user = Depends(get_current_user)):
            ...

    第三阶段 F2：增加 token type 校验，拒绝 refresh_token 被当作 access_token 使用。
    """
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
        # 校验 token 类型必须是 access（详见第三阶段 F2）
        token_type = payload.get("type")
        if token_type != "access":
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


async def require_superuser(current_user=Depends(get_current_user)):
    """要求当前用户是超级管理员，否则 403。"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此接口",
        )
    return current_user
