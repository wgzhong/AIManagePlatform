"""
依赖注入模块
将全局单例管理器通过 FastAPI Depends 注入，提升可测试性。
在测试环境中可通过覆盖依赖来 mock 任意组件。

使用方式:
    from app.dependencies import get_llm_infer
    @router.get("/test")
    async def handler(llm = Depends(get_llm_infer)):
        ...
"""

from app.core.llm_infer import LLMInfer, llm_infer as _llm_infer
from app.core.stats import StatsManager, stats_manager as _stats_manager
from app.core.devices import DeviceManager, device_manager as _device_manager
from app.core.api_keys import APIKeyManager, api_key_manager as _api_key_manager
from app.core.reminder_manager import ReminderManager, reminder_manager as _reminder_manager
from app.services.chat_service import ChatService
from app.services.device_service import DeviceService
from app.services.skill_service import SkillService
from app.services.reminder_service import ReminderService
from app.services.api_key_service import ApiKeyService


# ── LLM 推理客户端 ──

def get_llm_infer() -> LLMInfer:
    """获取 LLM 推理客户端实例"""
    return _llm_infer


# ── 统计管理器 ──

def get_stats_manager() -> StatsManager:
    """获取统计管理器实例"""
    return _stats_manager


# ── 设备管理器 ──

def get_device_manager() -> DeviceManager:
    """获取设备管理器实例"""
    return _device_manager


# ── API Key 管理器 ──

def get_api_key_manager() -> APIKeyManager:
    """获取 API Key 管理器实例"""
    return _api_key_manager


# ── 提醒管理器 ──

def get_reminder_manager() -> ReminderManager:
    """获取提醒管理器实例"""
    return _reminder_manager


# ── 服务层工厂（每次请求新建实例） ──

def get_chat_service() -> ChatService:
    """获取聊天服务实例"""
    return ChatService()


def get_device_service() -> DeviceService:
    """获取设备服务实例"""
    return DeviceService()


def get_skill_service() -> SkillService:
    """获取技能服务实例"""
    return SkillService()


def get_reminder_service() -> ReminderService:
    """获取提醒服务实例"""
    return ReminderService()


def get_api_key_service() -> ApiKeyService:
    """获取 API Key 服务实例"""
    return ApiKeyService()
