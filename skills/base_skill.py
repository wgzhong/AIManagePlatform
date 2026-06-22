"""
Skill 基类模块
定义所有 Skill 必须继承的基础类
支持从 md 文件加载配置和内容
"""

import os
import re
from typing import Dict, Any, Optional, List


class BaseSkill:
    """Skill 基类"""

    # 技能基本信息
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    icon: str = "🔧"
    category: str = "通用"

    # 高级配置选项
    enabled: bool = True
    auto_trigger: bool = False
    trigger_keywords: List[str] = []

    # System Prompt（可从 md 文件加载）
    system_prompt: str = ""
    mood_system_prompt: str = ""

    # skill 资源目录（子类通过相对路径引用）
    _skill_dir: Optional[str] = None

    def run(self, args: Dict[str, Any]) -> str:
        """
        执行技能，返回结果字符串

        Args:
            args: 技能执行所需的参数

        Returns:
            技能执行结果字符串
        """
        raise NotImplementedError("子类必须实现 run 方法")

    def get_tool_schema(self) -> Dict[str, Any]:
        """
        获取工具定义 Schema，用于 LLM 工具调用

        Returns:
            符合 OpenAI 工具调用格式的 Schema 字典
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def get_skill_dir(self) -> Optional[str]:
        """
        获取当前 skill 的目录路径
        通过类的模块信息获取
        """
        if self._skill_dir:
            return self._skill_dir

        # 通过类的模块获取路径
        import importlib
        module_name = self.__class__.__module__
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, '__file__') and module.__file__:
                module_path = os.path.abspath(module.__file__)
                skill_dir = os.path.dirname(module_path)
                return skill_dir
        except Exception:
            pass

        return None

    def _load_md_file(self, filename: str) -> str:
        """
        从 skill 目录下加载 md 文件内容

        Args:
            filename: md 文件名

        Returns:
            文件内容，如果不存在返回空字符串
        """
        skill_dir = self.get_skill_dir()
        if not skill_dir:
            return ""

        md_path = os.path.join(skill_dir, filename)
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _load_from_md_file(self) -> str:
        """
        从 _skill_path 加载 md 文件内容（去掉 YAML frontmatter）
        """
        skill_path = getattr(self, '_skill_path', None)
        if not skill_path or not os.path.isfile(skill_path):
            return ""

        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read()

            match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
            if match:
                return match.group(2).strip()
            return content.strip()
        except Exception:
            return ""

    def _save_md_file(self, filename: str, content: str) -> bool:
        """
        保存内容到 skill 目录下的 md 文件

        Args:
            filename: md 文件名
            content: 要保存的内容

        Returns:
            是否保存成功
        """
        skill_dir = self.get_skill_dir()
        if not skill_dir:
            return False

        md_path = os.path.join(skill_dir, filename)
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False

    def get_system_prompt(self) -> str:
        """
        获取该 skill 的 system prompt
        优先从 md 文件加载，其次使用类定义的值

        Returns:
            system prompt 字符串
        """
        skill_path = getattr(self, '_skill_path', None)
        if skill_path and os.path.isfile(skill_path):
            return self._load_from_md_file()
        md_content = self._load_md_file("skill.md")
        return md_content if md_content else self.system_prompt

    def get_mood_system_prompt(self, mood: str) -> Optional[str]:
        """
        获取该 skill 对应情绪的心情系统提示
        优先从 md 文件加载，其次使用类定义的值

        Args:
            mood: 情绪标识

        Returns:
            心情系统提示字符串，非情绪 skill 返回 None
        """
        skill_path = getattr(self, '_skill_path', None)
        if skill_path and os.path.isfile(skill_path):
            return self._load_from_md_file()
        md_content = self._load_md_file("skill.md")
        if md_content:
            return md_content
        return self.mood_system_prompt if self.mood_system_prompt else None

    def save_system_prompt(self, content: str) -> bool:
        """
        保存 system prompt 到 md 文件

        Args:
            content: 要保存的 system prompt 内容

        Returns:
            是否保存成功
        """
        return self._save_md_file("system_prompt.md", content)

    def save_mood_prompt(self, content: str) -> bool:
        """
        保存 mood prompt 到 md 文件

        Args:
            content: 要保存的 mood prompt 内容

        Returns:
            是否保存成功
        """
        return self._save_md_file("mood_prompt.md", content)

    def get_config_schema(self) -> Dict[str, Any]:
        """
        获取技能配置 Schema，用于网页端高级配置

        Returns:
            配置项定义字典
        """
        # 获取当前的 system prompt（从 md 或类字段）
        current_system_prompt = self.get_system_prompt()
        current_mood_prompt = self.get_mood_system_prompt(self.name.split("_")[0] if "_" in self.name else "")

        return {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "enabled": self.enabled,
            "auto_trigger": self.auto_trigger,
            "trigger_keywords": self.trigger_keywords,
            "parameters": self.parameters,
            "system_prompt": current_system_prompt,
            "mood_system_prompt": current_mood_prompt,
            "has_md_files": {
                "system_prompt": os.path.exists(os.path.join(self.get_skill_dir() or "", "system_prompt.md")) if self.get_skill_dir() else False,
                "mood_prompt": os.path.exists(os.path.join(self.get_skill_dir() or "", "mood_prompt.md")) if self.get_skill_dir() else False,
            }
        }

    def validate_args(self, args: Dict[str, Any]) -> bool:
        """
        验证参数是否符合要求

        Args:
            args: 待验证的参数

        Returns:
            参数是否有效
        """
        required = self.parameters.get("required", [])
        for param in required:
            if param not in args:
                return False
        return True


class MdSkill(BaseSkill):
    """从 md 文件加载的 Skill"""

    def __init__(self, md_path: str):
        self._skill_path = md_path
        self._load_from_frontmatter()

    def _load_from_frontmatter(self):
        """从 YAML frontmatter 加载配置"""
        if not self._skill_path:
            return

        try:
            with open(self._skill_path, "r", encoding="utf-8") as f:
                content = f.read()

            match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if match:
                frontmatter = match.group(1)
                self._parse_frontmatter(frontmatter)
        except Exception:
            pass

    def _parse_frontmatter(self, frontmatter: str):
        """解析 YAML frontmatter"""
        try:
            import yaml
            config = yaml.safe_load(frontmatter)
            if config and isinstance(config, dict):
                self.name = str(config.get("name", ""))
                self.description = str(config.get("description", ""))
                self.version = str(config.get("version", "1.0.0"))
                self.category = str(config.get("category", "通用"))
                self.icon = str(config.get("icon", "🔧"))
                self.enabled = bool(config.get("enabled", True))
                self.auto_trigger = bool(config.get("auto_trigger", False))

                keywords = config.get("trigger_keywords", [])
                if isinstance(keywords, str):
                    keywords = [k.strip() for k in keywords.strip("[]").split(",") if k.strip()]
                elif not isinstance(keywords, list):
                    keywords = []
                self.trigger_keywords = keywords

                params = config.get("parameters", {})
                if params and isinstance(params, dict):
                    self.parameters = params
            else:
                self._simple_parse(frontmatter)
        except ImportError:
            self._simple_parse(frontmatter)
        except Exception:
            self._simple_parse(frontmatter)

    def _simple_parse(self, frontmatter: str):
        """简单解析 YAML frontmatter（不依赖 PyYAML）"""
        for line in frontmatter.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            
            if key == "name":
                self.name = value
            elif key == "description":
                self.description = value
            elif key == "version":
                self.version = value
            elif key == "category":
                self.category = value
            elif key == "icon":
                self.icon = value
            elif key == "enabled":
                self.enabled = value.lower() == "true"
            elif key == "auto_trigger":
                self.auto_trigger = value.lower() == "true"
            elif key == "trigger_keywords":
                value = value.strip("[]")
                self.trigger_keywords = [k.strip().strip('"').strip("'") for k in value.split(",") if k.strip()]

    def run(self, args: Dict[str, Any]) -> str:
        """
        执行技能
        返回完整的 system prompt 内容，供 LLM 使用
        """
        return self.get_system_prompt()
