"""
Skill 基类模块
定义所有 Skill 必须继承的基础类
"""

import os
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
            import re
            content = re.sub(r'  \n', '\n', content)
            content = re.sub(r'(?<!\n)\n(?!\n)', '  \n', content)
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
        md_content = self._load_md_file("system_prompt.md")
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
        md_content = self._load_md_file("mood_prompt.md")
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
