"""
加密工具模块
提供 Fernet 对称加密，用于保护存储于磁盘的 API Key 等敏感数据。
加密密钥从配置项 ENCRYPTION_KEY 派生（回退到 ADMIN_TOKEN）。
若两者都未配置则回退为明文模式（打印警告日志）。

⚠️ 配置统一走 settings，不直接读 os.environ（详见 P0-1 修复）。
   密钥派生使用 PBKDF2HMAC + 固定 salt（防止字典攻击），替代旧的单层 SHA256。
"""

import base64
import logging

from app.core.config import get_effective_encryption_key

logger = logging.getLogger(__name__)

# 从配置派生加密种子
_ENCRYPTION_SEED = get_effective_encryption_key()

_fernet = None
if _ENCRYPTION_SEED:
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        # 用 PBKDF2HMAC 派生 32 字节密钥（10w 次迭代，防止暴力破解）
        # salt 固定值：本应用是单租户部署，无需每实例不同 salt；
        # 若改为多租户场景，应改为每实例随机 salt 并持久化。
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"aimanageplatform-fernet-salt-v1",
            iterations=100_000,
        )
        key_bytes = kdf.derive(_ENCRYPTION_SEED.encode("utf-8"))
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        _fernet = Fernet(fernet_key)
        logger.info("API Key 加密已启用（PBKDF2HMAC 派生密钥）")
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
