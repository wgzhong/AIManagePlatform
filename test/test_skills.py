﻿"""
Skill 加载和功能测试
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.skills import get_all_tool_definitions, get_skill_by_name, get_all_skill_configs, get_mood_system_prompt


def test_all_skills_loaded():
    """测试所有 skill 是否正确加载"""
    print("=== 所有技能 ===")
    configs = get_all_skill_configs()
    assert len(configs) > 0, "应该至少有一个技能"

    for config in configs:
        print(f"  - {config['name']}: {config['description']}")
        assert config['name'], "技能名称不能为空"
        assert config['description'], "技能描述不能为空"

    print(f"[OK] 共加载 {len(configs)} 个技能\n")


def test_mood_skills():
    """测试所有情绪 skill"""
    print("=== 情绪技能测试 ===")

    mood_skills = ['anger_mood', 'happy_mood', 'sad_mood', 'fear_mood', 'surprise_mood', 'disgust_mood', 'cheerful_mood']

    for skill_name in mood_skills:
        skill = get_skill_by_name(skill_name)
        assert skill is not None, f"技能 {skill_name} 应该存在"
        print(f"[OK] {skill_name}: 加载成功")

    print()


def test_mood_prompts():
    """测试所有情绪的 system prompt"""
    print("=== 情绪提示测试 ===")

    moods = ['anger', 'happy', 'sad', 'fear', 'surprise', 'disgust', 'cheerful']

    for mood in moods:
        prompt = get_mood_system_prompt(mood)
        assert prompt, f"情绪 {mood} 的提示不能为空"
        assert len(prompt) > 50, f"情绪 {mood} 的提示应该足够长"
        print(f"[OK] {mood}: {len(prompt)} 字符")

    print()


def test_tool_definitions():
    """测试工具定义格式"""
    print("=== 工具定义测试 ===")

    definitions = get_all_tool_definitions()
    assert len(definitions) > 0, "应该有工具定义"

    for defn in definitions:
        assert defn['type'] == 'function', "工具类型必须是 function"
        assert 'function' in defn, "必须有 function 字段"
        func = defn['function']
        assert 'name' in func, "必须有 name 字段"
        assert 'description' in func, "必须有 description 字段"
        assert 'parameters' in func, "必须有 parameters 字段"
        print(f"[OK] {func['name']}: 工具定义正确")

    print()


def test_calculate_skill():
    """测试计算器 skill"""
    print("=== 计算器测试 ===")
    skill = get_skill_by_name("calculate")
    assert skill is not None, "计算器 skill 应该存在"

    test_cases = [
        ({"expression": "2+3"}, "5"),
        ({"expression": "10-5"}, "5"),
        ({"expression": "3*4"}, "12"),
        ({"expression": "10/2"}, "5"),
    ]

    for args, expected in test_cases:
        result = skill.run(args)
        assert expected in result, f"计算 {args['expression']} 应该包含 {expected}，实际：{result}"
        print(f"[OK] {args['expression']} = {expected}")

    print()


def test_get_time_skill():
    """测试时间 skill"""
    print("=== 时间工具测试 ===")
    skill = get_skill_by_name("get_time")
    assert skill is not None, "时间 skill 应该存在"

    result = skill.run({"action": "get_time"})
    assert "现在" in result, "应该返回当前时间"
    print(f"[OK] get_time: {result}")

    print()


def test_get_weather_skill():
    """测试天气 skill"""
    print("=== 天气测试 ===")
    skill = get_skill_by_name("get_weather")
    assert skill is not None, "天气 skill 应该存在"

    result = skill.run({"city": "北京"})
    assert "北京" in result, "应该返回北京的天气"
    print(f"[OK] 北京: 天气信息正确")

    print()


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试...")
    print("=" * 60)
    print()

    test_all_skills_loaded()
    test_mood_skills()
    test_mood_prompts()
    test_tool_definitions()
    test_calculate_skill()
    test_get_time_skill()
    test_get_weather_skill()

    print("=" * 60)
    print("[OK] 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
