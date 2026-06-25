"""
/chat 端点：SSE 流式对话，支持 Skill 工具调用与 ESP32 设备码验证。
使用 ChatService 封装业务逻辑。
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.api.auth_deps import get_current_user
from app.middleware.rate_limit import limiter, RATE_LIMIT
from app.models.database import User
from app.services.chat_service import ChatService
from app.dependencies import get_chat_service

router = APIRouter()


@router.post("/chat")
@limiter.limit(RATE_LIMIT)
async def chat(
    request: Request,
    chat_request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_user)
):
    """处理聊天请求，支持 Skill 工具调用"""
    chat_request.user_id = current_user.id
    return StreamingResponse(service.process_chat(chat_request), media_type="text/event-stream")
