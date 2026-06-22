"""
运行所有测试
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test.test_skills import run_all_tests as run_skills_tests
from test.test_api import run_all_tests as run_api_tests
from test.test_llm import run_all_tests as run_llm_tests


def main():
    """运行所有测试套件"""
    print("\n" + "=" * 60)
    print("[AI Manage Platform] Test Suite")
    print("=" * 60)
    print()

    try:
        run_skills_tests()
        print()
    except Exception as e:
        print(f"[FAIL] Skill tests: {e}")
        return False

    try:
        run_api_tests()
        print()
    except Exception as e:
        print(f"[FAIL] API tests: {e}")
        return False

    try:
        run_llm_tests()
        print()
    except Exception as e:
        print(f"[FAIL] LLM tests: {e}")
        return False

    print("=" * 60)
    print("[SUCCESS] All test suites passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
