from .base_skill import BaseSkill

from .mandatory import GetTimeSkill, CalculateSkill, WeatherSkill

from .emotions import (
    AngerSkill,
    CheerfulSkill,
    DisgustSkill,
    FearSkill,
    HappySkill,
    SadSkill,
    SurpriseSkill
)

ALL_SKILLS = [
    GetTimeSkill(),
    CalculateSkill(),
    WeatherSkill(),
    AngerSkill(),
    CheerfulSkill(),
    DisgustSkill(),
    FearSkill(),
    HappySkill(),
    SadSkill(),
    SurpriseSkill()
]

_TOOL_DEFINITIONS_CACHE = None

def get_all_tool_definitions():
    global _TOOL_DEFINITIONS_CACHE
    if _TOOL_DEFINITIONS_CACHE is None:
        _TOOL_DEFINITIONS_CACHE = [skill.get_tool_schema() for skill in ALL_SKILLS]
    return _TOOL_DEFINITIONS_CACHE

def invalidate_tool_cache():
    """清除工具定义缓存，用于技能配置更新后"""
    global _TOOL_DEFINITIONS_CACHE
    _TOOL_DEFINITIONS_CACHE = None

def get_skill_by_name(name):
    for skill in ALL_SKILLS:
        if skill.name == name:
            return skill
    return None

def get_all_skill_configs():
    return [skill.get_config_schema() for skill in ALL_SKILLS]

__all__ = [
    "BaseSkill",
    "GetTimeSkill",
    "CalculateSkill",
    "WeatherSkill",
    "AngerSkill",
    "CheerfulSkill",
    "DisgustSkill",
    "FearSkill",
    "HappySkill",
    "SadSkill",
    "SurpriseSkill",
    "ALL_SKILLS",
    "get_all_tool_definitions",
    "get_skill_by_name",
    "get_all_skill_configs"
]
