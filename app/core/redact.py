"""
敏感信息脱敏工具。
统一处理 API Key / Token 等敏感字符串在响应中的展示。
"""

from typing import Optional


def mask_api_key(key: Optional[str]) -> str:
    """脱敏 API Key：保留前 6 位和后 4 位，中间用 ... 替代。

    示例：
        "abcdef1234567890" -> "abcdef...7890"
        "short"             -> "***"
        ""                  -> ""
        None                -> ""
    """
    if not key:
        return ""
    if len(key) < 12:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def mask_token(token: Optional[str]) -> str:
    """脱敏 JWT/Token：保留前 8 位和后 4 位。"""
    if not token:
        return ""
    if len(token) < 16:
        return "***"
    return f"{token[:8]}...{token[-4:]}"
