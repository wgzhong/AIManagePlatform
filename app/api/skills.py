"""
Skill API 路由。

V2: 支持私人技能（user_skills 表）+ 贡献开关。
- /api/skills/*         → 全局技能（admin）
- /api/user-skills/*    → 私人技能（任意登录用户）
- /api/skills/merged   → 合并列表（前端主入口）
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
import os
from sqlalchemy.orm import Session

from app.schemas.skills import (
    SkillConfigUpdate, SystemPromptRequest,
    SkillSystemPromptResponse, SkillFilePathResponse, CustomSkillCreate,
)
from app.schemas.auth import MessageResponse
from app.services.skill_service import SkillService, UserSkillService
from app.api.auth_deps import get_current_user
from app.middleware.auth import require_admin
from app.dependencies import get_skill_service
from app.models.database import get_db
from app.core.config import settings

router = APIRouter()


# =====================================================================
# 全局技能（admin 鉴权）
# =====================================================================

@router.get("/api/skills")
def get_skills(
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin),
):
    """返回所有全局技能列表（需 admin 鉴权）"""
    return service.get_all_skills()


@router.get("/api/skills/config")
def get_skills_config(
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin),
):
    """返回所有全局技能的完整配置信息（需 admin 鉴权）"""
    return service.get_skills_config()


@router.post("/api/skills/{skill_name}/config", response_model=MessageResponse)
def update_skill_config(
    skill_name: str,
    config: SkillConfigUpdate,
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin),
):
    """更新指定全局技能的配置（需 admin 鉴权）"""
    if not service.update_skill_config(skill_name, config.enabled, config.auto_trigger, config.trigger_keywords):
        raise HTTPException(status_code=404, detail="技能不存在")
    return MessageResponse(message=f"技能 {skill_name} 配置已更新")


@router.get("/api/skills/{skill_name}/system-prompt", response_model=SkillSystemPromptResponse)
def get_skill_system_prompt(
    skill_name: str,
    service: SkillService = Depends(get_skill_service),
):
    """获取指定全局技能的 system prompt 内容（公开可读，无需登录）"""
    result = service.get_skill_system_prompt(skill_name)
    if result is None:
        raise HTTPException(status_code=404, detail="技能不存在")
    return result


@router.post("/api/skills/{skill_name}/system-prompt", response_model=MessageResponse)
def save_skill_system_prompt(
    skill_name: str,
    request: SystemPromptRequest,
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin),
):
    """保存指定全局技能的 prompt 到 skill.md 文件（需 admin 鉴权）"""
    if not service.save_skill_system_prompt(skill_name, request.content):
        raise HTTPException(status_code=404, detail="技能不存在")
    return MessageResponse(message="Skill prompt 已保存到 md 文件")


@router.get("/api/skills/{skill_name}/file-path", response_model=SkillFilePathResponse)
def get_skill_file_path(
    skill_name: str,
    service: SkillService = Depends(get_skill_service),
):
    """获取指定全局技能的资源目录路径（公开可读，无需登录）"""
    result = service.get_skill_file_path(skill_name)
    if result is None:
        raise HTTPException(status_code=404, detail="技能不存在")
    return result


@router.post("/api/skills/custom")
def create_custom_skill(
    skill_data: CustomSkillCreate,
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin),
):
    """创建全局自定义技能（写入 skills/ 文件夹，需 admin 鉴权）"""
    result = service.create_custom_skill(skill_data, contribute=True)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
    return result


@router.delete("/api/skills/{skill_name}", response_model=MessageResponse)
def delete_global_skill(
    skill_name: str,
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin),
):
    """删除全局技能（需 admin 鉴权）"""
    result = service.delete_skill(skill_name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "删除失败"))
    return MessageResponse(message=result.get("message", f"技能 {skill_name} 已删除"))


@router.get("/api/skills/{skill_name}/raw-md")
def get_raw_md_content(
    skill_name: str,
    service: SkillService = Depends(get_skill_service),
):
    """获取全局技能完整 SKILL.md 原始内容（公开可读，无需登录）"""
    content = service.get_raw_md_content(skill_name)
    if content is None:
        raise HTTPException(status_code=404, detail="技能不存在或无 md 文件")
    return {"skill_name": skill_name, "raw_content": content, "source": "global"}


@router.post("/api/skills/{skill_name}/raw-md", response_model=MessageResponse)
def save_raw_md_content(
    skill_name: str,
    request: SystemPromptRequest,
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin),
):
    """保存全局技能完整 SKILL.md 内容（需 admin 鉴权）"""
    result = service.save_raw_md_content(skill_name, request.content)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "保存失败"))
    return MessageResponse(message=result.get("message"))


# =====================================================================
# 合并列表（前端主入口，需登录）
# =====================================================================

@router.get("/api/skills/merged")
def get_skills_merged(
    request: Request,
    db: Session = Depends(get_db),
    service: SkillService = Depends(get_skill_service),
):
    """
    返回全局技能 + 私人技能 + 贡献技能的合并列表（去重）。

    认证可选：
    - 有有效 token → 额外返回当前用户的私人技能（source='private'）
    - 无 token / token 过期 → 只返回全局技能 + 他人贡献的公开技能（只读）
    """
    from app.models.database import UserSkill
    from app.skills import ensure_contributed_skills_loaded

    # ── 懒加载已贡献技能到 ALL_SKILLS（服务器重启后恢复）───────────
    ensure_contributed_skills_loaded(db)

    # ── 尝试获取当前用户（可选，不抛 401）─────────────────────
    current_user = _try_get_current_user(db, request)

    result = service.get_all_skills()  # 全局技能

    # 标记所有全局技能为可读
    for s in result.get("skills", []):
        s.setdefault("source", "global")
        s.setdefault("readonly", False)

    # 标记 skills/custom/ 下的技能为 source='custom'
    # 使用与 skill_service.py 一致的路径计算方式（不依赖 settings.base_dir）
    _skills_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")
    _custom_dir = os.path.join(_skills_base, "custom")
    for s in result.get("skills", []):
        _sn = s.get("name", "")
        if _sn and os.path.isdir(os.path.join(_custom_dir, _sn)):
            s["source"] = "custom"
            # Admin 可编辑，其他用户只读
            s["readonly"] = not (current_user and getattr(current_user, "is_superuser", False))

    # 构建名称 → 索引映射，用于去重
    skill_name_map = {}
    for idx, s in enumerate(result["skills"]):
        sname = s.get("name") or s.get("skill_name", "")
        if sname:
            skill_name_map[sname] = idx

    global_names = set(skill_name_map.keys())
    current_user_id = current_user.id if current_user else None

    # ── 注入当前用户的私人技能（is_contributed=False）───────────
    if current_user_id:
        private_skills = db.query(UserSkill).filter(
            UserSkill.user_id == current_user_id,
            UserSkill.is_contributed == False,
        ).all()

        for ps in private_skills:
            if ps.name in skill_name_map:
                # 与全局技能重名：标记来源但不覆盖全局内容
                existing = result["skills"][skill_name_map[ps.name]]
                existing["_has_private"] = True
                existing["private_id"] = ps.id
            else:
                result["skills"].append({
                    "name": ps.name,
                    "description": ps.description or "",
                    "category": ps.category or "自定义",
                    "icon": ps.icon or "🔧",
                    "enabled": ps.enabled,
                    "auto_trigger": ps.auto_trigger or False,
                    "trigger_keywords": ps.trigger_keywords or [],
                    "source": "private",
                    "is_contributed": False,
                    "owner_id": ps.user_id,
                    "owner_name": current_user.username,
                    "readonly": False,
                    "db_id": ps.id,
                })
                skill_name_map[ps.name] = len(result["skills"]) - 1

    # ── 查询所有已贡献的公开技能 ──────────────────────────────
    contributed_others = db.query(UserSkill).filter(
        UserSkill.is_contributed == True,
    ).all()

    for cs in contributed_others:
        if cs.name in skill_name_map:
            existing = result["skills"][skill_name_map[cs.name]]
            # 已是私人技能则跳过（私人优先）
            if existing.get("source") == "private":
                continue
            # 已标记为 custom 技能则保留 custom 标签，只补充贡献信息
            if existing.get("source") == "custom":
                existing["is_contributed"] = True
                existing["owner_id"] = cs.user_id
                existing["owner_name"] = cs.user.username if cs.user else "未知用户"
                continue  # ← 关键：保留 source='custom'，不覆盖为 'contributed'
            existing["source"] = "contributed"
            existing["is_contributed"] = True
            existing["owner_id"] = cs.user_id
            existing["owner_name"] = cs.user.username if cs.user else "未知用户"
            if cs.user_id != current_user_id:
                existing["readonly"] = True
        elif cs.name not in global_names:
            result["skills"].append({
                "name": cs.name,
                "description": cs.description or "",
                "category": cs.category or "自定义",
                "icon": cs.icon or "🔧",
                "enabled": cs.enabled,
                "auto_trigger": cs.auto_trigger or False,
                "trigger_keywords": cs.trigger_keywords or [],
                "source": "contributed",
                "is_contributed": True,
                "owner_id": cs.user_id,
                "owner_name": cs.user.username if cs.user else "未知用户",
                "readonly": cs.user_id != current_user_id,
            })

    return result


def _try_get_current_user(db: Session, request=None):
    """尝试从请求头解析 JWT 获取当前用户；失败时返回 None（不抛异常）。"""
    try:
        if not request:
            return None
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]

        from jose import jwt, JWTError
        from app.services.user_service import SECRET_KEY, ALGORITHM, get_user_by_email
        from app.core.jwt_blacklist import is_blacklisted

        if not token or is_blacklisted(token):
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")
        if not email or token_type != "access":
            return None
        return get_user_by_email(db, email=email)
    except Exception:
        return None


# =====================================================================
# 私人技能（任意登录用户）
# =====================================================================

@router.get("/api/user-skills")
def list_user_skills(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出当前用户的所有私人技能"""
    user_svc = UserSkillService(db)
    return {"skills": user_svc.list_user_skills(current_user.id)}


@router.post("/api/user-skills")
def create_user_skill(
    skill_data: CustomSkillCreate,
    contribute: bool = Query(False, description="创建后是否立即贡献到全局技能库"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    创建私人技能（仅存数据库）。
    - contribute=True → 同时写入 skills/ 文件夹并标记为已贡献
    """
    user_svc = UserSkillService(db)
    result = user_svc.create_skill(skill_data, current_user.id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))

    # 若选择立即贡献
    if contribute and result.get("success"):
        user_svc.contribute(skill_data.name, current_user.id)

    return result


@router.get("/api/user-skills/{skill_name}")
def get_user_skill_detail(
    skill_name: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取私人技能详情"""
    user_svc = UserSkillService(db)
    skill = user_svc.get_skill(skill_name, current_user.id)
    if not skill:
        raise HTTPException(status_code=404, detail="私人技能不存在")
    return {
        "name": skill.name,
        "description": skill.description,
        "category": skill.category,
        "icon": skill.icon,
        "enabled": skill.enabled,
        "auto_trigger": skill.auto_trigger,
        "trigger_keywords": skill.trigger_keywords or [],
        "system_prompt": skill.system_prompt or "",
        "is_contributed": skill.is_contributed,
    }


@router.put("/api/user-skills/{skill_name}", response_model=MessageResponse)
def update_user_skill(
    skill_name: str,
    updates: dict = Body(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    更新私人技能（支持部分更新）。
    updates 中可以包含：description, category, icon, enabled,
    auto_triger, trigger_keywords, system_prompt 的任意组合。
    """
    from app.models.database import UserSkill

    skill = db.query(UserSkill).filter(
        UserSkill.user_id == current_user.id,
        UserSkill.name == skill_name,
    ).first()
    if not skill:
        raise HTTPException(status_code=404, detail="私人技能不存在")

    # 只更新提供的字段
    allowed = {"description", "category", "icon", "enabled",
               "auto_trigger", "trigger_keywords", "system_prompt"}
    for key, val in updates.items():
        if key in allowed and hasattr(skill, key):
            setattr(skill, key, val)

    db.commit()

    # 同步文件：已贡献的技能同步到 skills/ 文件夹；custom 技能始终同步到 skills/custom/ 目录
    # 检查是否是 custom 技能（contributed_skill_path 指向 skills/custom/ 目录）
    _should_sync = False
    if skill.is_contributed and skill.contributed_skill_path:
        _should_sync = True
    elif skill.contributed_skill_path and os.path.isfile(skill.contributed_skill_path):
        # custom 技能（未贡献）的文件也在 skills/custom/ 下，始终同步
        _should_sync = True

    if _should_sync:
        from app.services.skill_service import UserSkillService
        from app.skills import refresh_custom_skill_in_all_skills
        svc = UserSkillService(db)
        svc._sync_to_file(skill)
        # 刷新 ALL_SKILLS 内存中该技能的数据，确保 get_skills_merged() 返回最新配置
        try:
            refresh_custom_skill_in_all_skills(skill_name)
        except Exception:
            pass

    return MessageResponse(message=f"技能 {skill_name} 已更新")


@router.delete("/api/user-skills/{skill_name}", response_model=MessageResponse)
def delete_user_skill(
    skill_name: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除私人技能（若已贡献，同时从全局技能库移除）"""
    user_svc = UserSkillService(db)
    result = user_svc.delete_skill(skill_name, current_user.id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "删除失败"))
    return MessageResponse(message=result.get("message"))


# =====================================================================
# 贡献 / 取消贡献
# =====================================================================

@router.post("/api/user-skills/{skill_name}/contribute", response_model=MessageResponse)
def contribute_user_skill(
    skill_name: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将私人技能贡献到全局技能库（写入 skills/ 文件夹）"""
    user_svc = UserSkillService(db)
    result = user_svc.contribute(skill_name, current_user.id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "贡献失败"))
    return MessageResponse(message=result.get("message"))


@router.delete("/api/user-skills/{skill_name}/contribute", response_model=MessageResponse)
def uncontribute_user_skill(
    skill_name: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消贡献（从 skills/ 文件夹删除，但保留私人副本）"""
    user_svc = UserSkillService(db)
    result = user_svc.uncontribute(skill_name, current_user.id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "取消贡献失败"))
    return MessageResponse(message=result.get("message"))


# =====================================================================
# 私人技能 Raw MD（给前端编辑区使用）
# =====================================================================

@router.get("/api/user-skills/{skill_name}/raw-md")
def get_user_skill_raw_md(
    skill_name: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取私人技能完整 MD 内容（含 YAML frontmatter）"""
    user_svc = UserSkillService(db)
    content = user_svc.get_raw_md(skill_name, current_user.id)
    if content is None:
        raise HTTPException(status_code=404, detail="私人技能不存在")
    return {"skill_name": skill_name, "raw_content": content, "source": "private"}


@router.post("/api/user-skills/{skill_name}/raw-md", response_model=MessageResponse)
def save_user_skill_raw_md(
    skill_name: str,
    request: SystemPromptRequest = Body(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存私人技能完整 MD 内容"""
    user_svc = UserSkillService(db)
    result = user_svc.save_raw_md(skill_name, current_user.id, request.content)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "保存失败"))
    return MessageResponse(message=result.get("message"))
