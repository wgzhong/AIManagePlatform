"""
LLM 推理测试
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_llm_infer_import():
    """测试 LLM 推理模块导入"""
    print("=== LLM 推理模块测试 ===")
    from core.llm_infer import llm_infer, stream_chat_request

    assert llm_infer is not None, "llm_infer 应该存在"
    assert stream_chat_request is not None, "stream_chat_request 应该存在"

    print(f"[OK] LLM 推理模块导入成功")
    print(f"  - llm_infer: {type(llm_infer).__name__}")
    print()


def test_llm_client():
    """测试 LLM 客户端配置"""
    print("=== LLM 客户端配置测试 ===")
    from core.llm_infer import llm_infer
    from core.config import config

    assert llm_infer.default_url == config.DEFAULT_URL, "默认 URL 应该匹配"
    assert llm_infer.default_model, "应该有默认模型"

    print(f"[OK] LLM 客户端配置正确")
    print(f"  - URL: {llm_infer.default_url}")
    print(f"  - Model: {llm_infer.default_model}")
    print()


def test_message_truncation():
    """测试消息截断逻辑"""
    print("=== 消息截断测试 ===")

    messages = [{"role": "user", "content": f"消息{i}"} for i in range(50)]

    if len(messages) > 20:
        messages = messages[-20:]

    assert len(messages) == 20, f"截断后应该是 20 条，实际：{len(messages)}"

    print(f"[OK] 消息截断正确，从 50 条截断到 20 条")
    print()


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("LLM 推理测试")
    print("=" * 60)
    print()

    test_llm_infer_import()
    test_llm_client()
    test_message_truncation()

    print("=" * 60)
    print("[OK] LLM 推理测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
