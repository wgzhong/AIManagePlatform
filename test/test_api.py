"""
API 接口测试
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_api_keys():
    """测试 API Key 管理"""
    print("=== API Key 管理测试 ===")
    from core.api_keys import api_key_manager

    new_key = api_key_manager.generate_key()
    api_key_manager.add_key(new_key)

    keys_after = api_key_manager.load_keys()
    assert new_key in keys_after, "新 Key 应该被添加"

    is_valid = api_key_manager.validate_key(new_key)
    assert is_valid, "新 Key 应该有效"

    api_key_manager.remove_key(new_key)
    print(f"[OK] API Key 生成、验证、删除测试通过")


def test_devices():
    """测试设备管理"""
    print("=== 设备管理测试 ===")
    from core.devices import device_manager

    devices = device_manager.get_all_devices()
    assert isinstance(devices, dict), "设备列表应该是字典"
    print(f"[OK] 设备管理测试通过，当前 {len(devices)} 个设备")


def test_stats():
    """测试统计数据"""
    print("=== 统计数据测试 ===")
    from core.stats import stats_manager

    stats = stats_manager.load_stats()
    assert isinstance(stats, dict), "统计数据应该是字典"

    stats_manager.increment_request_count()
    print(f"[OK] 统计数据测试通过")


def test_chat_history():
    """测试对话历史"""
    print("=== 对话历史测试 ===")
    from core.chat_history import chat_history_manager

    history = chat_history_manager.load_history()
    assert isinstance(history, list), "对话历史应该是列表"
    print(f"[OK] 对话历史测试通过")


def test_reminders():
    """测试提醒管理"""
    print("=== 提醒管理测试 ===")
    from core.reminder_manager import reminder_manager

    message = "测试提醒"
    reminder_id = reminder_manager.set_reminder_in_minutes(message, 1)
    assert reminder_id, "应该返回提醒ID"

    reminder = reminder_manager.get_reminder(reminder_id)
    assert reminder is not None, "应该能获取到提醒"
    assert reminder['message'] == message, "消息应该匹配"

    print(f"[OK] 提醒管理测试通过，ID: {reminder_id}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("API 接口测试")
    print("=" * 60)
    print()

    test_api_keys()
    test_devices()
    test_stats()
    test_chat_history()
    test_reminders()

    print()
    print("=" * 60)
    print("[OK] 所有 API 测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
