"""
API Key 服务模块
封装 API Key 管理业务逻辑
"""

from typing import List

from app.core.api_keys import api_key_manager


class ApiKeyService:
    """API Key 服务类"""
    
    def generate_key(self) -> str:
        """生成新的 API Key"""
        new_key = api_key_manager.generate_key()
        api_key_manager.add_key(new_key)
        return new_key
    
    def list_keys(self) -> List[str]:
        """获取所有 API Keys"""
        return api_key_manager.load_keys()
    
    def delete_key(self, key: str) -> bool:
        """删除 API Key"""
        return api_key_manager.remove_key(key)
    
    def validate_key(self, key: str) -> bool:
        """验证 API Key"""
        if not key:
            return False
        return api_key_manager.validate_key(key)
