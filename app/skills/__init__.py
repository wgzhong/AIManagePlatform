"""
技能模块入口
自动扫描 skills/ 目录下的 md 文件加载技能
同时支持传统 Python 技能类
"""

import logging
import os
from typing import List, Dict, Optional

from .base_skill import BaseSkill, MdSkill

logger = logging.getLogger(__name__)


ALL_SKILLS: List[BaseSkill] = []
_TOOL_DEFINITIONS_CACHE = None


def _load_skills_from_md():
    """从 md 文件加载技能（扫描子目录下的 skill.md）"""
    skills_dir = os.path.dirname(__file__)
    
    existing_names = {skill.name for skill in ALL_SKILLS}
    
    for item in sorted(os.listdir(skills_dir)):
        item_path = os.path.join(skills_dir, item)
        if os.path.isdir(item_path):
            skill_md_path = os.path.join(item_path, "skill.md")
            if os.path.exists(skill_md_path):
                try:
                    skill = MdSkill(skill_md_path)
                    if skill.name and skill.name not in existing_names:
                        ALL_SKILLS.append(skill)
                except Exception as e:
                    logger.warning("加载 md 技能文件失败 %s: %s", skill_md_path, e)


def _load_python_skills():
    """加载 Python 技能类（需要实际执行逻辑的技能）"""
    try:
        from .get_time import GetTimeSkill
        ALL_SKILLS.append(GetTimeSkill())
    except ImportError:
        pass
    try:
        from .calculate import CalculateSkill
        ALL_SKILLS.append(CalculateSkill())
    except ImportError:
        pass
    try:
        from .get_weather import WeatherSkill
        ALL_SKILLS.append(WeatherSkill())
    except ImportError:
        pass


def _init_skills():
    """初始化所有技能"""
    if not ALL_SKILLS:
        _load_python_skills()
        _load_skills_from_md()


_init_skills()


def get_all_tool_definitions():
    """获取所有工具定义"""
    global _TOOL_DEFINITIONS_CACHE
    if _TOOL_DEFINITIONS_CACHE is None:
        _TOOL_DEFINITIONS_CACHE = [skill.get_tool_schema() for skill in ALL_SKILLS if skill.enabled]
    return _TOOL_DEFINITIONS_CACHE


def invalidate_tool_cache():
    """清除工具定义缓存，用于技能配置更新后"""
    global _TOOL_DEFINITIONS_CACHE
    _TOOL_DEFINITIONS_CACHE = None


def get_skill_by_name(name: str) -> Optional[BaseSkill]:
    """根据名称获取技能"""
    for skill in ALL_SKILLS:
        if skill.name == name:
            return skill
    return None


def get_all_skill_configs() -> List[Dict]:
    """获取所有技能配置"""
    return [skill.get_config_schema() for skill in ALL_SKILLS]


_MOOD_TO_SKILL_NAME = {
    "happy": "happy_mood",
    "cheerful": "cheerful_mood",
    "sad": "sad_mood",
    "anger": "anger_mood",
    "fear": "fear_mood",
    "disgust": "disgust_mood",
    "surprise": "surprise_mood",
}


def get_skill_by_mood(mood: str) -> Optional[BaseSkill]:
    """根据 mood 标识获取对应的 skill 实例"""
    skill_name = _MOOD_TO_SKILL_NAME.get(mood)
    if skill_name:
        return get_skill_by_name(skill_name)
    return None


def get_mood_system_prompt(mood: str) -> str:
    """
    根据 mood 获取对应的心情系统提示后缀
    先查找对应 skill，如果 skill 没有实现则使用默认提示
    """
    skill = get_skill_by_mood(mood)
    if skill:
        prompt = skill.get_mood_system_prompt(mood)
        if prompt:
            return prompt
    mood_labels = {
        "happy": "开心",
        "cheerful": "愉快",
        "sad": "难过",
        "anger": "生气",
        "fear": "害怕",
        "disgust": "厌恶",
        "surprise": "惊讶",
    }
    label = mood_labels.get(mood, mood)
    return f"你当前的心情是：{label}。请根据这个心情调整你的回复语气和表达方式。"


def reload_skills():
    """重新加载所有技能（用于热更新）"""
    ALL_SKILLS.clear()
    _init_skills()
    invalidate_tool_cache()


__all__ = [
    "BaseSkill",
    "MdSkill",
    "ALL_SKILLS",
    "get_all_tool_definitions",
    "get_skill_by_name",
    "get_all_skill_configs",
    "get_skill_by_mood",
    "get_mood_system_prompt",
    "reload_skills"
]
