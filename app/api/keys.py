"""
API Key 管理 API，全部加 admin 鉴权。
使用 ApiKeyService 封装业务逻辑，依赖注入统一走 app/dependencies.py。
（第三阶段 F1/F3 重构：async → def + 补 response_model）
"""

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.keys import ApiKeyGenerateResponse, ApiKeyListResponse, ApiKeyValidateResponse
from app.schemas.auth import MessageResponse
from app.services.api_key_service import ApiKeyService
from app.middleware.auth import require_admin
from app.dependencies import get_api_key_service

router = APIRouter()


@router.post("/api/keys/generate", response_model=ApiKeyGenerateResponse)
def generate_new_api_key(
    service: ApiKeyService = Depends(get_api_key_service),
    _: bool = Depends(require_admin),
):
    """生成新的随机 API Key"""
    new_key = service.generate_key()
    return ApiKeyGenerateResponse(key=new_key, message="API Key 生成成功")


@router.get("/api/keys", response_model=ApiKeyListResponse)
def list_api_keys(
    service: ApiKeyService = Depends(get_api_key_service),
    _: bool = Depends(require_admin),
):
    """列出所有可用的 API Keys"""
    return ApiKeyListResponse(keys=service.list_keys())


@router.delete("/api/keys/{key}", response_model=MessageResponse)
def delete_api_key(
    key: str,
    service: ApiKeyService = Depends(get_api_key_service),
    _: bool = Depends(require_admin),
):
    """删除指定的 API Key"""
    if not service.delete_key(key):
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return MessageResponse(message="API Key 删除成功")


@router.post("/api/keys/validate", response_model=ApiKeyValidateResponse)
def validate_api_key(
    key: str = None,
    service: ApiKeyService = Depends(get_api_key_service),
    _: bool = Depends(require_admin),
):
    """验证 API Key 是否有效"""
    return ApiKeyValidateResponse(valid=service.validate_key(key))
