"""
外部 API Key 管理 API
统一管理大模型/天气/导航等第三方服务密钥
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.provider_key_service import ProviderKeyService
from app.schemas.provider_keys import (
    ProviderKeyCreate,
    ProviderKeyListResponse,
    MessageResponse,
)
from app.api.auth_deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()
svc = ProviderKeyService()


# ── 分类与模板信息（公开接口，无需登录）──

@router.get("/api/provider-keys/meta")
def get_provider_keys_meta():
    """返回分类定义和预置模板（公开接口，仅静态配置信息）"""
    from app.schemas.provider_keys import CATEGORIES, PRESET_PROVIDERS
    return {"categories": CATEGORIES, "presets": PRESET_PROVIDERS}


# ── 以下所有端点需要登录 ──

# ── 列表 ──

@router.get("/api/provider-keys", response_model=ProviderKeyListResponse)
def list_provider_keys(
    category: Optional[str] = Query(None, description="分类筛选"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """列出所有外部 API Key（需登录）"""
    items, cat_stats = svc.list_keys(db, category)
    return ProviderKeyListResponse(
        keys=items,
        total=len(items),
        categories=cat_stats,
    )


# ── 详情（编辑回显） ──

@router.get("/api/provider-keys/{key_id}")
def get_provider_key_detail(
    key_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """获取单个 Key 详情（含加密密文，用于编辑回显）"""
    result = svc.get_key(db, key_id)
    if not result:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return result


# ── 创建 ──

@router.post("/api/provider-keys", response_model=MessageResponse)
def create_provider_key(
    data: ProviderKeyCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """创建新的外部 API Key"""
    from app.models.database import ExternalApiKey
    existing = db.query(ExternalApiKey).filter(
        ExternalApiKey.provider_code == data.provider_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"标识「{data.provider_code}」已存在，请使用不同的标识")
    result = svc.create_key(db, data.model_dump())
    return MessageResponse(message=f"✅ {data.provider_name} 已保存")


# ── 更新 ──

@router.put("/api/provider-keys/{key_id}", response_model=MessageResponse)
def update_provider_key(
    key_id: int,
    data: ProviderKeyCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """更新指定 API Key"""
    from app.models.database import ExternalApiKey
    record = db.query(ExternalApiKey).filter(ExternalApiKey.id == key_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    if data.provider_code != record.provider_code:
        dup = db.query(ExternalApiKey).filter(
            ExternalApiKey.provider_code == data.provider_code
        ).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"标识「{data.provider_code}」已被使用")

    result = svc.update_key(db, key_id, data.model_dump())
    if not result:
        raise HTTPException(status_code=404, detail="更新失败")
    return MessageResponse(message=f"✅ {data.provider_name} 已更新")


# ── 删除 ──

@router.delete("/api/provider-keys/{key_id}", response_model=MessageResponse)
def delete_provider_key(
    key_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """删除指定 API Key"""
    if not svc.delete_key(db, key_id):
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return MessageResponse(message="已删除")


# ── 启用/禁用切换 ──

@router.patch("/api/provider-keys/{key_id}/toggle")
def toggle_provider_key(
    key_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """切换启用/禁用状态"""
    result = svc.toggle_active(db, key_id)
    if not result:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return result


# ── 测试连接 ──

@router.post("/api/provider-keys/{key_id}/test")
def test_provider_key_connection(
    key_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """测试 Key 是否可用"""
    return svc.test_connection(db, key_id)
