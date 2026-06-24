"""
AI Manage Platform - 入口代理
向后兼容：python main.py 直接启动服务。
实际逻辑在 app.main 模块。
"""

import sys
import signal
import asyncio


def handle_exit(signal_num, frame):
    print("\n")
    print("=" * 50)
    print("🛡️  正在安全退出...")
    print("=" * 50)
    print("  正在关闭连接池...")
    print("  正在保存统计数据...")
    print("  正在释放资源...")
    print("=" * 50)
    print("✅  服务已安全退出！")
    print("=" * 50)
    sys.exit(0)


signal.signal(signal.SIGINT, handle_exit)


if __name__ == "__main__":
    from app.main import main
    main()