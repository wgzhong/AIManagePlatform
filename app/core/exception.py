"""
全局异常处理模块
定义统一的异常处理和错误响应格式
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from .response import ApiResponse


class AppException(Exception):
    """自定义应用异常"""
    
    def __init__(self, code: int = -1, message: str = "error", detail: dict = None):
        self.code = code
        self.message = message
        self.detail = detail or {}
        super().__init__(message)


class NotFoundException(AppException):
    """资源未找到异常"""
    
    def __init__(self, message: str = "资源未找到"):
        super().__init__(code=404, message=message)


class UnauthorizedException(AppException):
    """未授权异常"""
    
    def __init__(self, message: str = "未授权访问"):
        super().__init__(code=401, message=message)


class ForbiddenException(AppException):
    """禁止访问异常"""
    
    def __init__(self, message: str = "禁止访问"):
        super().__init__(code=403, message=message)


class BadRequestException(AppException):
    """请求参数错误异常"""
    
    def __init__(self, message: str = "请求参数错误"):
        super().__init__(code=400, message=message)


def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器"""
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.code if exc.code >= 400 else 200,
            content=ApiResponse.error(code=exc.code, message=exc.message).dict()
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error.get("loc", []))
            errors.append(f"{field}: {error.get('msg', '')}")
        return JSONResponse(
            status_code=400,
            content=ApiResponse.error(code=400, message="; ".join(errors)).dict()
        )
    
    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(request: Request, exc: ValidationError):
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error.get("loc", []))
            errors.append(f"{field}: {error.get('msg', '')}")
        return JSONResponse(
            status_code=400,
            content=ApiResponse.error(code=400, message="; ".join(errors)).dict()
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=ApiResponse.error(code=500, message=str(exc)).dict()
        )
