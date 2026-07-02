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
    """从 md 文件加载技能（递归扫描子目录下的 skill.md）
    
    注意：不扫描 skills/custom/ 目录！
    custom 目录下的技能只有贡献后才加入 ALL_SKILLS，
    由 contribute() 方法显式添加（并写入 skills/custom/ 目录）。
    这样未贡献的私人技能不会进入 ALL_SKILLS，不会对其他用户可见。
    """
    skills_dir = os.path.dirname(__file__)

    existing_names = {skill.name for skill in ALL_SKILLS}

    def _scan_dir(base_dir):
        """递归扫描目录中的 skill.md，遇到 custom/ 目录则跳过"""
        try:
            items = sorted(os.listdir(base_dir))
        except OSError:
            return
        for item in items:
            if item.startswith('.') or item == '__pycache__':
                continue
            # 跳过 custom/ 目录（不自动加载）
            if item == 'custom':
                continue
            item_path = os.path.join(base_dir, item)
            if os.path.isdir(item_path):
                # 先检查当前层是否有 skill.md（传统一级目录格式）
                skill_md_path = os.path.join(item_path, "skill.md")
                if os.path.exists(skill_md_path):
                    try:
                        skill = MdSkill(skill_md_path)
                        if skill.name and skill.name not in existing_names:
                            ALL_SKILLS.append(skill)
                            existing_names.add(skill.name)
                    except Exception as e:
                        logger.warning("加载 md 技能文件失败 %s: %s", skill_md_path, e)
                else:
                    # 没有 skill.md，继续递归深入
                    _scan_dir(item_path)

    _scan_dir(skills_dir)


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
    try:
        from .homeassistant import HomeAssistantSkill
        ALL_SKILLS.append(HomeAssistantSkill())
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


# ---------------------------------------------------------------------------
# 贡献技能懒加载（服务器重启后恢复）
# ---------------------------------------------------------------------------
_CONTRIBUTED_LOADED = False


def ensure_contributed_skills_loaded(db=None):
    """
    确保已贡献的技能加载进 ALL_SKILLS。
    服务器重启后 custom/ 目录不再自动扫描，需要通过此函数恢复。
    在 get_skills_merged() 中调用（传入 db session）。
    """
    global _CONTRIBUTED_LOADED
    if _CONTRIBUTED_LOADED:
        return

    if db is None:
        return

    from app.models.database import UserSkill
    contributed = db.query(UserSkill).filter(
        UserSkill.is_contributed == True,
    ).all()

    existing_names = {s.name for s in ALL_SKILLS}
    skills_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'skills')
    skills_base = os.path.normpath(skills_base)

    for rec in contributed:
        if rec.name in existing_names:
            continue
        skill_dir = os.path.join(skills_base, 'custom', rec.name)
        skill_md = os.path.join(skill_dir, 'skill.md')
        if os.path.isfile(skill_md):
            try:
                from .base_skill import MdSkill
                skill = MdSkill(skill_md)
                if skill.name:
                    ALL_SKILLS.append(skill)
                    existing_names.add(skill.name)
            except Exception as e:
                logger.warning("恢复贡献技能失败 %s: %s", skill_md, e)

    _CONTRIBUTED_LOADED = True


def reset_contributed_loaded_flag():
    """用于在测试中重置标志，正常情况下不需要调用"""
    global _CONTRIBUTED_LOADED
    _CONTRIBUTED_LOADED = False


def refresh_custom_skill_in_all_skills(skill_name: str):
    """
    刷新 ALL_SKILLS 中某个 custom 技能的内存数据，从其 skill.md 文件重新加载。
    当 user_skills API 更新了 skills/custom/ 下的文件后，调用此函数确保
    get_skills_merged() 返回的是最新配置，无需完整 reload_skills()。
    """
    skills_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'skills')
    skills_base = os.path.normpath(skills_base)
    skill_md = os.path.join(skills_base, 'custom', skill_name, 'skill.md')
    if not os.path.isfile(skill_md):
        return False
    # 如果技能已在 ALL_SKILLS 中，重新加载它
    for i, skill in enumerate(ALL_SKILLS):
        if skill.name == skill_name:
            try:
                from .base_skill import MdSkill
                new_skill = MdSkill(skill_md)
                ALL_SKILLS[i] = new_skill
                invalidate_tool_cache()
                return True
            except Exception as e:
                logger.warning("刷新 custom 技能失败 %s: %s", skill_md, e)
                return False
    # 如果技能不在 ALL_SKILLS 中（例如服务器重启后），但文件存在，则添加它
    try:
        from .base_skill import MdSkill
        new_skill = MdSkill(skill_md)
        if new_skill.name:
            ALL_SKILLS.append(new_skill)
            invalidate_tool_cache()
            return True
    except Exception as e:
        logger.warning("添加 custom 技能到 ALL_SKILLS 失败 %s: %s", skill_md, e)
    return False


__all__ = [
    "BaseSkill",
    "MdSkill",
    "ALL_SKILLS",
    "get_all_tool_definitions",
    "get_skill_by_name",
    "get_all_skill_configs",
    "get_skill_by_mood",
    "get_mood_system_prompt",
    "reload_skills",
    "ensure_contributed_skills_loaded",
    "reset_contributed_loaded_flag",
    "refresh_custom_skill_in_all_skills",
]
