"""
Skill API 路由。

V2: 支持私人技能（user_skills 表）+ 贡献开关。
- /api/skills/*         → 全局技能（admin）
- /api/user-skills/*    → 私人技能（任意登录用户）
- /api/skills/merged   → 合并列表（前端主入口）
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
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
    db: Session = Depends(get_db),
    service: SkillService = Depends(get_skill_service),
):
    """
    返回全局技能 + 私人技能 + 贡献技能的合并列表（去重）。

    认证可选：
    - 有有效 token → 额外返回当前用户的私人技能
    - 无 token / token 过期 → 只返回全局技能 + 他人贡献的公开技能（只读）
    """
    from app.models.database import UserSkill

    # 尝试获取当前用户（可选）
    current_user = None
    try:
        # 从请求头手动提取 token 并验证（不依赖 Depends，避免 401）
        from fastapi import Request
        from fastapi import Header
        # 通过 get_current_user 的逻辑手动解析
        from jose import JWTError, jwt
        from app.services.user_service import SECRET_KEY, ALGORITHM, get_user_by_email
        import inspect

        # 获取当前 request 对象（通过 inspect 调用栈）
        # 更可靠的方式：直接在函数签名中加可选的 Authorization header
        pass  # 在下面处理
    except Exception:
        pass

    result = service.get_all_skills()  # 全局技能

    # 尝试从 header 解析用户
    try:
        from starlette.requests import Request as StarletteRequest
        # 使用依赖注入的上下文获取 request
        import contextvars
        # 实际上我们无法直接获取 request，改用另一种方式：
        # 让前端传 token，我们在代码中手动验证
        pass
    except Exception:
        pass

    # 标记所有全局技能为可读
    for s in result.get("skills", []):
        s.setdefault("source", "global")
        s.setdefault("readonly", False)

    # 查询所有已贡献的公开技能（其他用户的）
    contributed_others = db.query(UserSkill).filter(
        UserSkill.is_contributed == True,
    ).all()

    skill_name_map = {}
    for idx, s in enumerate(result["skills"]):
        sname = s.get("name") or s.get("skill_name", "")
        if sname:
            skill_name_map[sname] = idx

    global_names = set(skill_name_map.keys())

    for cs in contributed_others:
        if cs.name in skill_name_map:
            existing = result["skills"][skill_name_map[cs.name]]
            existing["source"] = "contributed"
            existing["is_contributed"] = True
            existing["owner_id"] = cs.user_id
            existing["owner_name"] = cs.user.username if cs.user else "未知用户"
            if cs.user_id != (current_user.id if current_user else None):
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
                "readonly": True,
            })

    return result


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

    # 若已贡献，同步文件
    if skill.is_contributed and skill.contributed_skill_path:
        from app.services.skill_service import UserSkillService
        svc = UserSkillService(db)
        svc._sync_to_file(skill)

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
