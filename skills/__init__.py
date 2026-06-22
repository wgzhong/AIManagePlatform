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

# mood 标识到 skill name 的映射
_MOOD_TO_SKILL_NAME = {
    "happy": "happy_response",
    "cheerful": "cheerful_response",
    "sad": "sad_response",
    "anger": "anger_response",
    "fear": "fear_response",
    "disgust": "disgust_response",
    "surprise": "surprise_response",
}

def get_skill_by_mood(mood: str):
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
    # 默认提示
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
    "get_all_skill_configs",
    "get_skill_by_mood",
    "get_mood_system_prompt"
]
