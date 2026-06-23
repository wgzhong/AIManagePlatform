"""
技能服务模块
封装技能管理业务逻辑
"""

import os
from typing import Optional

from app.skills import (
    get_all_skill_configs,
    get_skill_by_name,
    invalidate_tool_cache,
)
from app.schemas.skills import SkillSystemPromptResponse, SkillFilePathResponse


class SkillService:
    """技能服务类"""
    
    def get_all_skills(self):
        """获取所有技能配置"""
        configs = get_all_skill_configs()
        return {"skills": configs, "protocol": "Skill-2025-06-18"}
    
    def get_skills_config(self):
        """获取所有技能配置信息"""
        configs = get_all_skill_configs()
        return {"configs": configs}
    
    def update_skill_config(self, skill_name: str, enabled: bool = None, 
                            auto_trigger: bool = None, trigger_keywords: list = None) -> bool:
        """更新技能配置"""
        skill = get_skill_by_name(skill_name)
        if not skill:
            return False
        
        if enabled is not None:
            skill.enabled = enabled
        if auto_trigger is not None:
            skill.auto_trigger = auto_trigger
        if trigger_keywords is not None:
            skill.trigger_keywords = trigger_keywords
        
        invalidate_tool_cache()
        return True
    
    def get_skill_system_prompt(self, skill_name: str) -> Optional[SkillSystemPromptResponse]:
        """获取技能的 system prompt"""
        skill = get_skill_by_name(skill_name)
        if not skill:
            return None
        
        mood = skill_name.split("_")[0] if "_" in skill_name and skill_name.endswith("_mood") else ""
        mood_system_prompt = skill.get_mood_system_prompt(mood) if mood else None
        
        skill_path = getattr(skill, "_skill_path", None)
        has_md = skill_path is not None and os.path.isfile(skill_path)
        
        return SkillSystemPromptResponse(
            skill_name=skill_name,
            system_prompt=skill.get_system_prompt(),
            mood_system_prompt=mood_system_prompt,
            has_md_files={
                "system_prompt": has_md,
                "mood_prompt": has_md,
            },
        )
    
    def save_skill_system_prompt(self, skill_name: str, content: str) -> bool:
        """保存技能的 system prompt"""
        skill = get_skill_by_name(skill_name)
        if not skill:
            return False
        
        success = skill.save_system_prompt(content)
        if success:
            invalidate_tool_cache()
        
        return success
    
    def get_skill_file_path(self, skill_name: str) -> Optional[SkillFilePathResponse]:
        """获取技能文件路径"""
        skill = get_skill_by_name(skill_name)
        if not skill:
            return None
        
        skill_path = getattr(skill, "_skill_path", None)
        return SkillFilePathResponse(
            skill_name=skill_name,
            skill_path=skill_path,
            skill_dir=skill.get_skill_dir(),
            md_file_path=skill_path if skill_path and os.path.isfile(skill_path) else None,
        )
