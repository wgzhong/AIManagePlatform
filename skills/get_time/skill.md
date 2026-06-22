---
name: get_time
description: 获取当前时间、日期，设置定时提醒和闹钟
version: 1.0.0
category: 工具
icon: ⏰
enabled: true
auto_trigger: true
trigger_keywords: ["时间", "几点", "日期", "提醒", "闹钟", "定时"]
parameters:
  type: object
  required: []
  properties:
    action:
      type: string
      description: 操作类型，可选值：get_time（获取时间）、set_reminder（设置提醒）、cancel_reminder（取消提醒）、list_reminders（查看提醒列表）
    minutes:
      type: integer
      description: 多少分钟后提醒
    hour:
      type: integer
      description: 提醒时间（小时）
    minute:
      type: integer
      description: 提醒时间（分钟）
    message:
      type: string
      description: 提醒消息内容
    reminder_id:
      type: string
      description: 要取消的提醒ID
---

# 时间工具技能

## 功能说明
提供时间查询和定时提醒功能，帮助用户管理时间和设置提醒。

## 使用场景
1. **获取当前时间**：用户询问"现在几点"、"今天几号"等
2. **设置定时提醒**：用户说"N分钟后叫我"、"下午3点提醒我"等
3. **取消提醒**：用户说"取消提醒"、"删除闹钟"等
4. **查看提醒列表**：用户说"我有哪些提醒"、"查看闹钟"等

## 输出格式
- 获取时间：直接返回当前时间和日期
- 设置提醒：返回提醒ID和触发时间
- 取消提醒：返回操作结果
- 查看列表：列出所有待执行的提醒

## 示例
**用户输入**：现在几点了
**你的回答**：现在是 2026年06月21日 15:30

**用户输入**：10分钟后叫我
**你的回答**：⏰ 已设置提醒！将在 10 分钟后（15:40）提醒你：提醒时间到了！
提醒ID：abc1234

**用户输入**：下午3点提醒我开会
**你的回答**：⏰ 已设置闹钟！将在 2026年06月21日 15:00 提醒你：开会
提醒ID：def5678

**用户输入**：我有哪些提醒
**你的回答**：📋 待执行的提醒：
1. [abc1234] 2026-06-21 15:40 - 提醒时间到了！
2. [def5678] 2026-06-21 15:00 - 开会

**用户输入**：取消提醒 abc1234
**你的回答**：✅ 已取消提醒：abc1234

## 错误处理
- 无法识别操作类型时，默认返回当前时间
- 设置提醒缺少必要参数时，提示用户补充信息
- 取消不存在的提醒时，提示用户提醒不存在
