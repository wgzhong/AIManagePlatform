"""
/chat 端点：SSE 流式对话，支持 Skill 工具调用与 ESP32 设备码验证。
使用 ChatService 封装业务逻辑。
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.api.auth import get_current_user
from app.models.database import User

router = APIRouter()


def get_chat_service() -> ChatService:
    return ChatService()


@router.post("/chat")
async def chat(
    request: ChatRequest, 
    service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_user)
):
    """处理聊天请求，支持 Skill 工具调用"""
    print("request.model = ", request.model)
    request.user_id = current_user.id
    return StreamingResponse(service.process_chat(request), media_type="text/event-stream")
