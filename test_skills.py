from skills import get_all_tool_definitions, get_skill_by_name, get_all_skill_configs

print("=== 所有技能 ===")
configs = get_all_skill_configs()
for config in configs:
    print(f"  - {config['name']}: {config['description']}")

print("\n=== 情绪技能测试 ===")
anger_skill = get_skill_by_name("anger_response")
print(f"愤怒响应: {anger_skill.run({'text': '我很生气！'})}")

cheerful_skill = get_skill_by_name("cheerful_response")
print(f"开心响应: {cheerful_skill.run({'text': '今天真开心！'})}")

sad_skill = get_skill_by_name("sad_response")
print(f"悲伤响应: {sad_skill.run({'text': '我很难过'})}")

fear_skill = get_skill_by_name("fear_response")
print(f"恐惧响应: {fear_skill.run({'text': '我好害怕'})}")

surprise_skill = get_skill_by_name("surprise_response")
print(f"惊讶响应: {surprise_skill.run({'text': '哇！真没想到！'})}")

disgust_skill = get_skill_by_name("disgust_response")
print(f"厌恶响应: {disgust_skill.run({'text': '真恶心'})}")

happy_skill = get_skill_by_name("happy_response")
print(f"快乐响应: {happy_skill.run({'text': '我很快乐'})}")

print("\n=== 所有测试通过! ===")