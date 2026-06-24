"""
Skill 工具列表与配置 API。
使用 SkillService 封装业务逻辑。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.schemas.skills import SkillConfigUpdate, SystemPromptRequest, SkillSystemPromptResponse, SkillFilePathResponse, CustomSkillCreate
from app.services.skill_service import SkillService
from app.middleware.auth import require_admin

router = APIRouter()


def get_skill_service() -> SkillService:
    return SkillService()


@router.get("/api/skills")
async def get_skills(service: SkillService = Depends(get_skill_service)):
    """返回所有注册的 Skill 工具列表"""
    return service.get_all_skills()


@router.get("/api/skills/config")
async def get_skills_config(service: SkillService = Depends(get_skill_service)):
    """返回所有技能的完整配置信息"""
    return service.get_skills_config()


@router.post("/api/skills/{skill_name}/config")
async def update_skill_config(
    skill_name: str, config: SkillConfigUpdate, 
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin)
):
    """更新指定技能的配置（需 admin 鉴权）"""
    if not service.update_skill_config(skill_name, config.enabled, config.auto_trigger, config.trigger_keywords):
        raise HTTPException(status_code=404, detail="技能不存在")
    return {"success": True, "message": f"技能 {skill_name} 配置已更新"}


@router.get("/api/skills/{skill_name}/system-prompt", response_model=SkillSystemPromptResponse)
async def get_skill_system_prompt(skill_name: str, service: SkillService = Depends(get_skill_service)):
    """获取指定技能的 system prompt 内容"""
    result = service.get_skill_system_prompt(skill_name)
    if result is None:
        raise HTTPException(status_code=404, detail="技能不存在")
    return result


@router.post("/api/skills/{skill_name}/system-prompt")
async def save_skill_system_prompt(
    skill_name: str, request: SystemPromptRequest, 
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin)
):
    """保存指定技能的 prompt 到 skill.md 文件（需 admin 鉴权）"""
    if not service.save_skill_system_prompt(skill_name, request.content):
        raise HTTPException(status_code=404, detail="技能不存在")
    return {"success": True, "message": "Skill prompt 已保存到 md 文件"}


@router.get("/api/skills/{skill_name}/file-path", response_model=SkillFilePathResponse)
async def get_skill_file_path(skill_name: str, service: SkillService = Depends(get_skill_service)):
    """获取指定技能的资源目录路径"""
    result = service.get_skill_file_path(skill_name)
    if result is None:
        raise HTTPException(status_code=404, detail="技能不存在")
    return result


@router.post("/api/skills/custom")
async def create_custom_skill(
    skill_data: CustomSkillCreate,
    service: SkillService = Depends(get_skill_service),
    _: bool = Depends(require_admin)
):
    """创建自定义技能（需 admin 鉴权）"""
    result = service.create_custom_skill(skill_data)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
    return result
