"""
统一日志配置模块
配置全局日志格式和处理器
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Optional


def setup_logging(log_level: str = "INFO", log_dir: Optional[str] = None):
    """
    设置全局日志配置
    
    Args:
        log_level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_dir: 日志文件目录，默认为项目根目录下的 logs 目录
    """
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    if logger.handlers:
        logger.handlers.clear()
    
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    logger.addHandler(console_handler)
    
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level.upper()))
    logger.addHandler(file_handler)
    
    return logger


logger = setup_logging()
