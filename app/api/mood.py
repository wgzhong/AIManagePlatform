"""
心情提示 API。
"""

from fastapi import APIRouter

from app.schemas.mood import MoodPromptResponse
from app.skills import get_mood_system_prompt

router = APIRouter()


@router.get("/api/mood-prompt/{mood}", response_model=MoodPromptResponse)
def get_mood_prompt_api(mood: str):
    """获取指定心情的 prompt 内容"""
    prompt = get_mood_system_prompt(mood)
    return MoodPromptResponse(mood=mood, prompt=prompt)
