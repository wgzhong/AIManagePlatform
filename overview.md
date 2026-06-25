# 工具调用修复 - 最终方案（2026-06-25）

## 问题现象
用户问「几点了」，AI 回复："哇！让我帮你看看现在几点啦！🕐"，**但不调用 `get_time` 工具**，直接返回了文本。

## 根因（最终确认）
`tool_choice` 参数已正确传入（`{"type": "function", "function": {"name": "get_time"}}`），
但 **GLM API 对 `tool_choice` 的支持有问题**，LLM 始终选择不调工具，直接生成文本回复。

→ 光靠 `tool_choice` 参数不可靠，**不能依赖 LLM 来触发工具调用**。

## 最终修复方案：后端强制直接执行

**核心思路**：关键词命中时，**后端直接执行技能**，不等待 LLM 返回 tool_calls。
执行完后用 LLM 润色结果返回（第二次 LLM 调用不带 tools，避免循环）。

### 执行流程
```
用户问「几点了」
  → 关键词检测命中「几点」
  → 强制 tool_choice = {"type": "function", "function": {"name": "get_time"}}
  → 后端直接调用 get_time.run({"action": "get_time"})
  → 得到结果：「现在是 2026年06月25日 16:35」
  → 调用 LLM（tools=None）润色：「现在是下午 4 点 35 分啦～⏰」
  → 流式返回给用户
```

### 如果技能执行失败
- `skill.run()` 抛异常 → `skill_result = None`
- 回退到正常 LLM 流程（可能还是不调工具，但至少不会崩溃）

## 修改的文件

### `app/services/chat_service.py`（主修复）
1. **新增 `_parse_skill_args()` 方法**：根据技能名从用户消息解析参数
2. **新增强制工具执行逻辑**（在 `process_chat` 中，LLM 调用之前）：
   - 检测 `forced_skill_name`
   - 直接执行 `skill.run()`
   - LLM 润色（不带 tools）
   - `return` 跳过正常流程
3. **Debug 日志**：`logger.info()` + `print()` 双重输出，确保能看到

### `app/core/llm_client.py`
- `debug_log()`：`logger.debug()` → `logger.info()`，避免被日志级别过滤

### `app/core/llm_stream.py`
- payload 构造时打印 `tool_choice` 值（debug）
- 前 3 个 SSE chunk 打印完整原始数据（debug）
- tool_calls 收到时打印确认（debug）

## 测试步骤
1. 重启服务：`cd D:\pywork\AIManagePlatform && python -m uvicorn app.main:app --reload`
2. 打开首页，进入对话
3. 发送：「几点了」
4. 预期结果：
   - 控制台输出 `[TOOL-DEBUG] 🔧🔧🔧 强制直接执行工具: get_time`
   - 控制台输出 `[TOOL-DEBUG] 工具执行结果: 现在是 2026年06月25日 16:35`
   - 聊天框显示时间（格式由 LLM 润色）

## 支持的技能
| 关键词 | 技能 | 说明 |
|--------|------|------|
| 时间/几点/日期/现在/今天 | `get_time` | 获取当前时间 |
| 计算/等于/加减乘除 | `calculate` | 数学计算 |
| 天气/温度/下雨 | `get_weather` | 天气查询 |
