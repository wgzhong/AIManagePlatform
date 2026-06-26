"""
外部 API Key 管理 — 请求/响应模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── 分类常量 ──

CATEGORIES = {
    "llm": {"label": "大模型 LLM", "icon": "🤖", "color": "#72e0e0"},
    "weather": {"label": "天气服务", "icon": "🌤️", "color": "#4ade80"},
    "navigation": {"label": "导航地图", "icon": "🗺️", "color": "#fb923c"},
    "search": {"label": "搜索引擎", "icon": "🔍", "color": "#a78bfa"},
    "translation": {"label": "翻译服务", "icon": "🌐", "color": "#f472b6"},
    "storage": {"label": "云存储", "icon": "☁️", "color": "#38bdf8"},
    "notification": {"label": "消息推送", "icon": "📬", "color": "#facc15"},
    "other": {"label": "其他", "icon": "🔑", "color": "#9898aa"},
}

# 预置模板（用户可快速添加常用服务商）
PRESET_PROVIDERS = [
    {"code": "zhipu", "name": "智谱 AI (Zhipu)", "category": "llm", "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions", "models": ["glm-4.6v", "glm-5.1", "glm-4.5-air"]},
    {"code": "openai", "name": "OpenAI", "category": "llm", "url": "https://api.openai.com/v1/chat/completions", "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"]},
    {"code": "anthropic", "name": "Anthropic (Claude)", "category": "llm", "url": "https://api.anthropic.com/v1/messages", "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"]},
    {"code": "deepseek", "name": "DeepSeek", "category": "llm", "url": "https://api.deepseek.com/chat/completions", "models": ["deepseek-chat", "deepseek-reasoner"]},
    {"code": "qwen", "name": "通义千问 (Qwen)", "category": "llm", "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "models": ["qwen3-turbo", "qwen3-max", "qwen-vl-plus"]},
    {"code": "doubao", "name": "豆包 (Doubao)", "category": "llm", "url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions", "models": "请填写火山引擎 Endpoint ID"},
    {"code": "moonshot", "name": "Moonshot (Kimi)", "category": "llm", "url": "https://api.moonshot.cn/v1/chat/completions", "models": ["moonshot-v1-auto", "moonshot-v1-128k", "moonshot-v1-32k"]},
    {"code": "gaode_weather", "name": "高德天气", "category": "weather", "url": "https://restapi.amap.com/v3/weather/weatherInfo", "models": []},
    {"code": "hefeng_weather", "name": "和风天气", "category": "weather", "url": "https://devapi.qweather.com/v7/weather/now", "models": []},
    {"code": "gaode_map", "name": "高德地图", "category": "navigation", "url": "https://restapi.amap.com/v3/geocode/geo", "models": []},
    {"code": "baidu_map", "name": "百度地图", "category": "navigation", "url": "https://map.baidu.com/", "models": []},
]


class ProviderKeyCreate(BaseModel):
    """创建 / 更新外部 API Key"""
    provider_name: str = Field(..., min_length=1, max_length=100, description="显示名称")
    provider_code: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$", description="唯一标识（小写字母数字下划线）")
    category: str = Field(default="other", description="分类")
    key_value: str = Field(..., min_length=1, description="API Key 值（明文，后端会加密）")
    api_url: Optional[str] = Field("", max_length=500, description="API 地址")
    models: Optional[List[str]] = Field(default=[], description="关联模型列表")
    is_active: bool = Field(True, description="是否启用")
    priority: int = Field(0, ge=0, le=100, description="优先级")
    description: Optional[str] = Field("", max_length=500, description="备注")


class ProviderKeyResponse(BaseModel):
    """单个 Key 的响应（密文脱敏）"""
    id: int
    provider_name: str
    provider_code: str
    category: str
    key_masked: str                    # 脱敏后的 key：sk-****abcd
    api_url: str
    models: List[str]
    is_active: bool
    priority: int
    description: str
    created_at: datetime
    updated_at: datetime


class ProviderKeyDetailResponse(ProviderKeyResponse):
    """详情响应（含完整密文——仅用于编辑回显）"""
    key_value: str                     # 加密后的完整值


class ProviderKeyListResponse(BaseModel):
    """列表响应"""
    keys: List[ProviderKeyResponse]
    total: int
    categories: dict                   # 各分类统计


class MessageResponse(BaseModel):
    message: str
