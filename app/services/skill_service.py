"""
技能服务模块
封装技能管理业务逻辑

V2: 支持私人技能（存数据库）+ 贡献开关（存 skills/ 文件夹）
"""

import os
import json
import logging
import shutil
import re
from typing import Optional

logger = logging.getLogger(__name__)

from app.skills import (
    get_all_skill_configs,
    get_skill_by_name,
    invalidate_tool_cache,
    reload_skills,
)
from app.skills.base_skill import MdSkill
from app.schemas.skills import SkillSystemPromptResponse, SkillFilePathResponse, CustomSkillCreate


# ---------------------------------------------------------------------------
# 辅助：从完整 MD 文本解析 YAML frontmatter
# ---------------------------------------------------------------------------

def _parse_skill_md(content: str) -> dict:
    """解析 skill.md 完整内容，返回字段字典"""
    result = {
        "description": "",
        "category": "自定义",
        "icon": "🔧",
        "enabled": True,
        "auto_trigger": False,
        "trigger_keywords": [],
        "system_prompt": "",
    }
    if not content.startswith('---'):
        return result

    parts = content.split('---', 2)
    if len(parts) < 3:
        return result

    frontmatter = parts[1]
    result["system_prompt"] = parts[2].strip()

    for line in frontmatter.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip()
            if key == 'description':
                result["description"] = val
            elif key == 'category':
                result["category"] = val
            elif key == 'icon':
                result["icon"] = val
            elif key == 'enabled':
                result["enabled"] = val.lower() in ('true', '1', 'yes')
            elif key == 'auto_trigger':
                result["auto_trigger"] = val.lower() in ('true', '1', 'yes')
            elif key == 'trigger_keywords':
                try:
                    result["trigger_keywords"] = json.loads(val)
                except Exception:
                    # 尝试解析 YAML 数组格式: [ "a", "b" ]
                    arr = []
                    if val.startswith('[') and val.endswith(']'):
                        for item in val[1:-1].split(','):
                            item = item.strip().strip('"').strip("'")
                            if item:
                                arr.append(item)
                    result["trigger_keywords"] = arr

    return result


# ---------------------------------------------------------------------------
# 全局技能服务（文件型，原有逻辑保留）
# ---------------------------------------------------------------------------

class SkillService:
    """全局技能服务（skills/ 文件夹 + 内建 Python 技能）"""

    def get_all_skills(self):
        """获取所有全局技能配置"""
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

        mood = skill_name.split('_')[0] if '_' in skill_name and skill_name.endswith('_mood') else ''
        mood_system_prompt = skill.get_mood_system_prompt(mood) if mood else None

        skill_path = getattr(skill, '_skill_path', None)
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

        skill_path = getattr(skill, '_skill_path', None)
        return SkillFilePathResponse(
            skill_name=skill_name,
            skill_path=skill_path,
            skill_dir=skill.get_skill_dir(),
            md_file_path=skill_path if skill_path and os.path.isfile(skill_path) else None,
        )

    # ------------------------------------------------------------------
    # 创建自定义技能（V2：支持 contribute 开关）
    # ------------------------------------------------------------------
    def create_custom_skill(self, data: CustomSkillCreate,
                           user_id: int = None,
                           contribute: bool = False) -> dict:
        """
        创建自定义技能。
        - contribute=True  → 写入 skills/ 文件夹（全局可见）
        - contribute=False + user_id → 写入 user_skills 表（仅该用户）
        - contribute=False + no user_id → 默认写入 skills/ 文件夹（向后兼容）
        """
        if contribute or not user_id:
            return self._create_global_skill(data)
        else:
            return self._create_private_skill(data, user_id)

    def _create_global_skill(self, data: CustomSkillCreate) -> dict:
        """写入 skills/ 文件夹（原有逻辑）"""
        from app.skills import ALL_SKILLS

        if not re.match(r'^[a-zA-Z0-9_\-]+$', data.name):
            return {"success": False, "message": "技能名称只能包含英文、数字、下划线和连字符"}

        existing = get_skill_by_name(data.name)
        if existing:
            return {"success": False, "message": f"技能 {data.name} 已存在"}

        safe_category = re.sub(r'[<>:"/\\|?*]', '_', data.category).strip() or "自定义"

        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        skills_base_dir = os.path.join(app_dir, "skills")

        skill_dir = os.path.join(skills_base_dir, safe_category, data.name)
        os.makedirs(skill_dir, exist_ok=True)

        keywords_yaml = "[" + ", ".join(f'"{kw}"' for kw in data.trigger_keywords) + "]"

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

        # 注册到运行内存
        try:
            new_skill = MdSkill(skill_md_path)
            if new_skill.name:
                ALL_SKILLS.append(new_skill)
                invalidate_tool_cache()
        except Exception:
            logger.exception("MdSkill 加载失败，回退到 reload_skills: %s", skill_md_path)
            reload_skills()

        return {"success": True, "message": f"技能 {data.name} 创建成功", "skill_name": data.name, "source": "global"}

    def _create_private_skill(self, data: CustomSkillCreate, user_id: int) -> dict:
        """写入 user_skills 表（私人技能）"""
        from sqlalchemy.orm import Session
        from app.models.database import UserSkill

        # 接受 db session（通过 self.db 或参数传入）
        # 这里需要从调用方传入 db，暂时用导入方式
        # 实际由 API 层调用 user_skill_service，不走此处
        return {"success": False, "message": "请使用 UserSkillService 创建私人技能"}

    def delete_skill(self, skill_name: str) -> dict:
        """删除全局技能（仅支持 md 文件型）"""
        from app.skills import ALL_SKILLS

        skill = get_skill_by_name(skill_name)
        if not skill:
            return {"success": False, "message": f"技能 {skill_name} 不存在"}

        skill_path = getattr(skill, '_skill_path', None)
        is_python_builtin = (
            skill_path is None
            or not skill_path.endswith('.md')
            or not os.path.isfile(skill_path)
        )

        if is_python_builtin:
            return {
                "success": False,
                "message": f"内建技能 {skill_name} 不支持删除（仅可删除自定义 md 技能）"
            }

        # 从运行内存移除
        ALL_SKILLS[:] = [s for s in ALL_SKILLS if s.name != skill_name]
        invalidate_tool_cache()

        # 删除文件和目录
        try:
            skill_dir = os.path.dirname(skill_path)
            if os.path.isdir(skill_dir):
                shutil.rmtree(skill_dir)
                logger.info("已删除技能目录: %s", skill_dir)
        except Exception as e:
            logger.exception("删除技能目录失败: %s", skill_dir)
            return {"success": True, "message": f"技能 {skill_name} 已从列表移除，但文件清理失败: {e}"}

        return {"success": True, "message": f"技能 {skill_name} 已删除"}

    def get_raw_md_content(self, skill_name: str) -> Optional[str]:
        """获取全局技能的完整 SKILL.md 原始内容"""
        skill = get_skill_by_name(skill_name)
        if not skill:
            return None

        skill_path = getattr(skill, '_skill_path', None)
        if skill_path and os.path.isfile(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                return f.read()

        return None

    def save_raw_md_content(self, skill_name: str, content: str) -> dict:
        """保存全局技能的完整 SKILL.md 内容"""
        skill = get_skill_by_name(skill_name)
        if not skill:
            return {"success": False, "message": f"技能 {skill_name} 不存在"}

        skill_path = getattr(skill, '_skill_path', None)
        if not skill_path or not os.path.isfile(skill_path):
            return {
                "success": False,
                "message": f"技能 {skill_name} 没有 skill.md 文件（内建技能不支持直接编辑 md 文件）"
            }

        try:
            with open(skill_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 重新加载该技能以更新配置
            from app.skills import ALL_SKILLS
            for i, s in enumerate(ALL_SKILLS):
                if s.name == skill_name:
                    try:
                        reloaded = type(s)(skill_path) if isinstance(s, MdSkill) else s
                        ALL_SKILLS[i] = reloaded
                    except Exception:
                        pass
                    break

            invalidate_tool_cache()
            return {"success": True, "message": "SKILL.md 已保存"}
        except Exception as e:
            logger.exception("保存 SKILL.md 失败: %s", skill_path)
            return {"success": False, "message": f"保存失败: {e}"}


# ---------------------------------------------------------------------------
# 私人技能服务（数据库型，per-user）
# ---------------------------------------------------------------------------

class UserSkillService:
    """私人技能服务（user_skills 表）"""

    def __init__(self, db):
        self.db = db

    # ----------------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------------
    def list_user_skills(self, user_id: int) -> list:
        """列出用户所有私人技能"""
        from app.models.database import UserSkill

        records = self.db.query(UserSkill).filter(
            UserSkill.user_id == user_id
        ).order_by(UserSkill.created_at.desc()).all()

        return [{
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "category": r.category,
            "icon": r.icon,
            "enabled": r.enabled,
            "auto_trigger": r.auto_trigger,
            "trigger_keywords": r.trigger_keywords or [],
            "source": "private",
            "is_contributed": r.is_contributed,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        } for r in records]

    def get_skill(self, skill_name: str, user_id: int):
        """获取单个私人技能"""
        from app.models.database import UserSkill

        return self.db.query(UserSkill).filter(
            UserSkill.user_id == user_id,
            UserSkill.name == skill_name,
        ).first()

    def create_skill(self, data: CustomSkillCreate, user_id: int) -> dict:
        """创建私人技能（仅存数据库，不写入 skills/ 文件夹）"""
        from app.models.database import UserSkill

        if not re.match(r'^[a-zA-Z0-9_\-]+$', data.name):
            return {"success": False, "message": "技能名称只能包含英文、数字、下划线和连字符"}

        existing = self.db.query(UserSkill).filter(
            UserSkill.user_id == user_id,
            UserSkill.name == data.name,
        ).first()
        if existing:
            return {"success": False, "message": f"你已有一个名为 {data.name} 的私人技能"}

        user_skill = UserSkill(
            user_id=user_id,
            name=data.name,
            description=data.description,
            category=data.category,
            icon=data.icon,
            enabled=data.enabled,
            auto_trigger=data.auto_trigger,
            trigger_keywords=data.trigger_keywords,
            system_prompt=data.system_prompt,
            is_contributed=False,
        )
        self.db.add(user_skill)
        self.db.commit()

        return {
            "success": True,
            "message": f"私人技能 {data.name} 创建成功",
            "skill_name": data.name,
            "source": "private",
        }

    def update_skill(self, skill_name: str, data: CustomSkillCreate, user_id: int) -> dict:
        """更新私人技能"""
        from app.models.database import UserSkill

        user_skill = self.db.query(UserSkill).filter(
            UserSkill.user_id == user_id,
            UserSkill.name == skill_name,
        ).first()
        if not user_skill:
            return {"success": False, "message": "找不到该私人技能"}

        user_skill.description = data.description
        user_skill.category = data.category
        user_skill.icon = data.icon
        user_skill.enabled = data.enabled
        user_skill.auto_trigger = data.auto_trigger
        user_skill.trigger_keywords = data.trigger_keywords
        user_skill.system_prompt = data.system_prompt
        self.db.commit()

        # 如果已贡献，同步更新 skills/ 文件夹中的文件
        if user_skill.is_contributed and user_skill.contributed_skill_path:
            self._sync_to_file(user_skill)

        return {"success": True, "message": f"私人技能 {skill_name} 已更新"}

    def delete_skill(self, skill_name: str, user_id: int) -> dict:
        """删除私人技能（若已贡献，同时从 skills/ 文件夹删除）"""
        from app.models.database import UserSkill

        user_skill = self.db.query(UserSkill).filter(
            UserSkill.user_id == user_id,
            UserSkill.name == skill_name,
        ).first()
        if not user_skill:
            return {"success": False, "message": "找不到该私人技能"}

        # 若已贡献，从 skills/ 文件夹删除
        if user_skill.is_contributed and user_skill.contributed_skill_path:
            self._remove_from_file(user_skill)

        self.db.delete(user_skill)
        self.db.commit()

        return {"success": True, "message": f"私人技能 {skill_name} 已删除"}

    # ----------------------------------------------------------------
    # 贡献 / 取消贡献
    # ----------------------------------------------------------------
    def contribute(self, skill_name: str, user_id: int) -> dict:
        """
        将私人技能贡献到全局技能库：
        1. 写入 skills/<category>/<name>/skill.md
        2. 注册到 ALL_SKILLS
        3. 标记 is_contributed=True
        """
        from app.models.database import UserSkill
        from app.skills import ALL_SKILLS

        user_skill = self.db.query(UserSkill).filter(
            UserSkill.user_id == user_id,
            UserSkill.name == skill_name,
        ).first()
        if not user_skill:
            return {"success": False, "message": "找不到该私人技能"}
        if user_skill.is_contributed:
            return {"success": False, "message": "该技能已贡献到全局技能库"}

        # 写入 skills/ 文件夹
        skill_md_path = self._write_to_file(user_skill)
        if not skill_md_path:
            return {"success": False, "message": "写入 skills/ 文件夹失败"}

        # 注册到运行内存
        try:
            new_skill = MdSkill(skill_md_path)
            if new_skill.name:
                ALL_SKILLS.append(new_skill)
                invalidate_tool_cache()
        except Exception:
            logger.exception("MdSkill 加载失败: %s", skill_md_path)
            reload_skills()

        user_skill.is_contributed = True
        user_skill.contributed_skill_path = skill_md_path
        self.db.commit()

        return {"success": True, "message": f"技能 {skill_name} 已贡献到全局技能库"}

    def uncontribute(self, skill_name: str, user_id: int) -> dict:
        """
        取消贡献：
        1. 从 skills/ 文件夹删除
        2. 从 ALL_SKILLS 移除
        3. 标记 is_contributed=False
        """
        from app.models.database import UserSkill
        from app.skills import ALL_SKILLS

        user_skill = self.db.query(UserSkill).filter(
            UserSkill.user_id == user_id,
            UserSkill.name == skill_name,
        ).first()
        if not user_skill:
            return {"success": False, "message": "找不到该技能"}
        if not user_skill.is_contributed:
            return {"success": False, "message": "该技能未贡献"}

        # 从 skills/ 文件夹删除
        self._remove_from_file(user_skill)

        # 从运行内存移除
        ALL_SKILLS[:] = [s for s in ALL_SKILLS if s.name != skill_name]
        invalidate_tool_cache()

        user_skill.is_contributed = False
        user_skill.contributed_skill_path = ""
        self.db.commit()

        return {"success": True, "message": f"技能 {skill_name} 已取消贡献"}

    # ----------------------------------------------------------------
    # MD 内容读取 / 保存（用于前端 Raw MD 编辑）
    # ----------------------------------------------------------------
    def get_raw_md(self, skill_name: str, user_id: int) -> Optional[str]:
        """获取私人技能的完整 MD 内容（用于编辑区展示）"""
        user_skill = self.get_skill(skill_name, user_id)
        if not user_skill:
            return None
        return self._build_md_content(user_skill)

    def save_raw_md(self, skill_name: str, user_id: int, content: str) -> dict:
        """从完整 MD 内容解析并保存私人技能"""
        from app.models.database import UserSkill

        user_skill = self.db.query(UserSkill).filter(
            UserSkill.user_id == user_id,
            UserSkill.name == skill_name,
        ).first()
        if not user_skill:
            return {"success": False, "message": "找不到该私人技能"}

        parsed = _parse_skill_md(content)
        user_skill.description = parsed["description"]
        user_skill.category = parsed["category"]
        user_skill.icon = parsed["icon"]
        user_skill.enabled = parsed["enabled"]
        user_skill.auto_trigger = parsed["auto_trigger"]
        user_skill.trigger_keywords = parsed["trigger_keywords"]
        user_skill.system_prompt = parsed["system_prompt"]
        self.db.commit()

        # 若已贡献，同步文件
        if user_skill.is_contributed and user_skill.contributed_skill_path:
            self._sync_to_file(user_skill)

        return {"success": True, "message": "私人技能已保存"}

    # ----------------------------------------------------------------
    # 内部辅助
    # ----------------------------------------------------------------
    def _build_md_content(self, user_skill) -> str:
        """从 UserSkill 记录构建完整 MD 文本"""
        keywords_yaml = json.dumps(user_skill.trigger_keywords or [], ensure_ascii=False)
        return f"""---
name: {user_skill.name}
description: {user_skill.description}
version: 1.0.0
category: {user_skill.category}
icon: {user_skill.icon}
enabled: {"true" if user_skill.enabled else "false"}
auto_trigger: {"true" if user_skill.auto_trigger else "false"}
trigger_keywords: {keywords_yaml}
---

{user_skill.system_prompt}
"""

    def _write_to_file(self, user_skill) -> Optional[str]:
        """将私人技能写入 skills/ 文件夹，返回文件路径"""
        safe_category = re.sub(r'[<>:"/\\|?*]', '_', user_skill.category).strip() or "自定义"
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        skills_base_dir = os.path.join(app_dir, "skills")
        skill_dir = os.path.join(skills_base_dir, safe_category, user_skill.name)
        os.makedirs(skill_dir, exist_ok=True)

        content = self._build_md_content(user_skill)
        skill_md_path = os.path.join(skill_dir, "skill.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(content)
        return skill_md_path

    def _sync_to_file(self, user_skill) -> None:
        """已贡献的技能，同步更新 skills/ 文件夹中的文件"""
        if not user_skill.contributed_skill_path:
            self._write_to_file(user_skill)
            return
        content = self._build_md_content(user_skill)
        with open(user_skill.contributed_skill_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _remove_from_file(self, user_skill) -> None:
        """从 skills/ 文件夹删除已贡献的技能"""
        if user_skill.contributed_skill_path and os.path.isfile(user_skill.contributed_skill_path):
            skill_dir = os.path.dirname(user_skill.contributed_skill_path)
            if os.path.isdir(skill_dir):
                shutil.rmtree(skill_dir)


# ---------------------------------------------------------------------------
# 聊天时加载当前用户的私人技能（返回临时 skill 对象，供 chat_service 使用）
# ---------------------------------------------------------------------------

def load_user_skills_for_chat(user_id: int, db) -> list:
    """
    加载当前用户的私人技能，返回类似 BaseSkill 的轻量对象列表，
    供 chat_service 做 trigger 匹配和 skill.run() 调用。
    """
    from app.models.database import UserSkill

    records = db.query(UserSkill).filter(
        UserSkill.user_id == user_id,
        UserSkill.enabled.is_(True),
    ).all()

    results = []
    for r in records:
        obj = _UserSkillProxy(r)
        results.append(obj)
    return results


class _UserSkillProxy:
    """
    轻量代理对象，模拟 BaseSkill 接口，
    使私人技能可以无缝接入现有 chat_service 的触发和调用逻辑。
    """
    def __init__(self, db_record):
        self._record = db_record
        self.name = db_record.name
        self.description = db_record.description
        self.category = db_record.category
        self.icon = db_record.icon
        self.enabled = db_record.enabled
        self.auto_trigger = db_record.auto_trigger
        self.trigger_keywords = db_record.trigger_keywords or []

    def run(self, args: dict) -> str:
        return self._record.system_prompt or ""

    def get_system_prompt(self) -> str:
        return self._record.system_prompt or ""

    def get_mood_system_prompt(self, mood: str):
        return None

    def save_system_prompt(self, content: str) -> bool:
        return False

    def get_skill_dir(self) -> str:
        return ""

    @property
    def _skill_path(self):
        return None
