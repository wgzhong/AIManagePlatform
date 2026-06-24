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
    reload_skills,
)
from app.skills.base_skill import MdSkill
from app.schemas.skills import SkillSystemPromptResponse, SkillFilePathResponse, CustomSkillCreate


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
    
    def create_custom_skill(self, data: CustomSkillCreate) -> dict:
        """创建自定义技能"""
        from app.skills import ALL_SKILLS
        import re
        
        # 校验技能名：只允许英文、数字、下划线、连字符
        if not re.match(r'^[a-zA-Z0-9_\-]+$', data.name):
            return {"success": False, "message": "技能名称只能包含英文、数字、下划线和连字符"}
        
        # 检查是否已存在
        existing = get_skill_by_name(data.name)
        if existing:
            return {"success": False, "message": f"技能 {data.name} 已存在"}
        
        # 清理 category，用于目录名
        safe_category = re.sub(r'[<>:"/\\|?*]', '_', data.category).strip()
        if not safe_category:
            safe_category = "自定义"
        
        # 确定 skills 目录路径
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        skills_base_dir = os.path.join(app_dir, "skills")
        
        # 创建目录
        skill_dir = os.path.join(skills_base_dir, safe_category, data.name)
        os.makedirs(skill_dir, exist_ok=True)
        
        # 构建 keywords YAML 数组
        keywords_yaml = "[" + ", ".join(f'"{kw}"' for kw in data.trigger_keywords) + "]"
        
        # 写入 skill.md
        skill_md_content = f"""---
name: {data.name}
description: {data.description}
version: 1.0.0
category: {data.category}
icon: {data.icon}
enabled: {"true" if data.enabled else "false"}
auto_trigger: {"true" if data.auto_trigger else "false"}
trigger_keywords: {keywords_yaml}
---

{data.system_prompt}
"""
        skill_md_path = os.path.join(skill_dir, "skill.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(skill_md_content)
        
        # 注册技能到运行内存
        try:
            new_skill = MdSkill(skill_md_path)
            if new_skill.name:
                ALL_SKILLS.append(new_skill)
                invalidate_tool_cache()
        except Exception:
            # 如果 MdSkill 加载失败，用 reload_skills 兜底
            reload_skills()
        
        return {"success": True, "message": f"技能 {data.name} 创建成功", "skill_name": data.name}
