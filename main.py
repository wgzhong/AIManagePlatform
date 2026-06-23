"""
AI Manage Platform - 入口代理
向后兼容：python main.py 直接启动服务。
实际逻辑在 app.main 模块。
"""

from app.main import main

if __name__ == "__main__":
    main()
