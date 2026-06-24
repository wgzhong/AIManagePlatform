"""
技能管理相关的请求/响应模型
"""

from typing import Optional, List
from pydantic import BaseModel


class SkillConfigUpdate(BaseModel):
    """技能配置更新请求模型"""
    enabled: Optional[bool] = None
    auto_trigger: Optional[bool] = None
    trigger_keywords: Optional[List[str]] = None


class SystemPromptRequest(BaseModel):
    """System Prompt 更新请求模型"""
    content: str
    prompt_type: str = "system_prompt"


class SkillSystemPromptResponse(BaseModel):
    """技能 System Prompt 响应模型"""
    skill_name: str
    system_prompt: str
    mood_system_prompt: Optional[str]
    has_md_files: dict


class SkillFilePathResponse(BaseModel):
    """技能文件路径响应模型"""
    skill_name: str
    skill_path: Optional[str]
    skill_dir: Optional[str]
    md_file_path: Optional[str]


class CustomSkillCreate(BaseModel):
    """自定义技能创建请求模型"""
    name: str
    description: str
    icon: str = "🔧"
    category: str = "自定义"
    system_prompt: str = ""
    enabled: bool = True
    auto_trigger: bool = False
    trigger_keywords: List[str] = []
