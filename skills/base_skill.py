"""
Skill 基类模块
定义所有 Skill 必须继承的基础类
"""

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
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        获取技能配置 Schema，用于网页端高级配置
        
        Returns:
            配置项定义字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "enabled": self.enabled,
            "auto_trigger": self.auto_trigger,
            "trigger_keywords": self.trigger_keywords,
            "parameters": self.parameters
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