"""
统一响应模型模块
定义全局统一的 API 响应格式
"""

from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[T] = None

    @classmethod
    def success(cls, data: T = None, message: str = "success") -> 'ApiResponse[T]':
        """创建成功响应"""
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, code: int = -1, message: str = "error") -> 'ApiResponse':
        """创建错误响应"""
        return cls(code=code, message=message, data=None)


class PageResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    items: List[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 10
