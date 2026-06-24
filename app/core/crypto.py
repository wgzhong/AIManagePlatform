"""
加密工具模块
提供 Fernet 对称加密，用于保护存储于磁盘的 API Key 等敏感数据。
加密密钥从环境变量 ENCRYPTION_KEY 或 ADMIN_TOKEN 派生。
若未配置则回退为明文模式（打印警告日志）。
"""
import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

# 从环境变量获取加密种子，未配置则为空（明文模式）
_ENCRYPTION_SEED = os.environ.get("ENCRYPTION_KEY") or os.environ.get("ADMIN_TOKEN", "")

_fernet = None
if _ENCRYPTION_SEED:
    try:
        from cryptography.fernet import Fernet
        # 用 SHA256 将任意长度种子派生为 32 字节，再 base64 编码为 Fernet key
        key_bytes = hashlib.sha256(_ENCRYPTION_SEED.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        _fernet = Fernet(fernet_key)
        logger.info("API Key 加密已启用")
    except ImportError:
        logger.warning("cryptography 库未安装，API Key 将明文存储。安装: pip install cryptography")
else:
    logger.warning(
        "ENCRYPTION_KEY 或 ADMIN_TOKEN 未设置，API Key 将明文存储。"
        "生产环境请务必设置 ENCRYPTION_KEY 环境变量。"
    )


def encrypt(text: str) -> str:
    """加密字符串，返回 base64 编码的密文；明文模式返回原文加前缀标记"""
    if not text:
        return text
    if _fernet is not None:
        return _fernet.encrypt(text.encode("utf-8")).decode("utf-8")
    # 明文模式：加前缀标记便于识别
    return f"plain:{text}"


def decrypt(token: str) -> str:
    """解密字符串；明文模式去掉前缀标记"""
    if not token:
        return token
    if _fernet is not None and not token.startswith("plain:"):
        try:
            return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.warning("解密失败: %s", e)
            return token
    if token.startswith("plain:"):
        return token[6:]
    return token
