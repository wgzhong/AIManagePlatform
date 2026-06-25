# 第一阶段修复总结

> 完成时间：2026-06-25
> 对应报告：`code-review-report.md` 第一阶段（安全与正确性）

## 修复清单

| 编号 | 问题 | 修改文件 | 状态 |
| ---- | ---- | ---- | ---- |
| **P0-1** | 配置读取双轨制导致 ADMIN_TOKEN 静默失效 | `app/core/config.py`、`app/middleware/auth.py`、`app/core/crypto.py`、`app/middleware/rate_limit.py`、`app/main.py` | ✅ |
| **P0-2** | `ChatService` 每请求新建实例导致 `asyncio.Lock` 失效 | `app/core/devices.py`、`app/services/chat_service.py` | ✅ |
| **P0-5** | 管理员接口明文返回所有用户 API Key | `app/core/redact.py`（新增）、`app/api/auth.py` | ✅ |
| **S5** | `validate_key` 非常量时间比较 | `app/core/api_keys.py` | ✅ |
| **S8** | `/api/health` 无鉴权可被滥用 | `app/api/stats.py` | ✅ |
| **Q1** | `llm_utils.py` 死代码 + 裸 `except:` | 删除 `app/core/llm_utils.py` | ✅ |
| **README** | UTF-16 LE 编码 + 内容不全 | `README.md` 重写为 UTF-8 | ✅ |

## 详细修改说明

### P0-1：配置双轨制修复

**根因**：项目用 `pydantic-settings` 从 `.env` 文件读取配置到 `settings` 对象，但 4 个模块仍直接调 `os.environ.get`。当用户按 `.env.example` 推荐方式部署（仅写 `.env`、不注入系统环境变量）时，这些 `os.environ.get` 全部返回空，导致：
- `ADMIN_TOKEN` 为空 → 管理接口鉴权被静默关闭
- `_ENCRYPTION_SEED` 为空 → API Key 明文存储
- `RATE_LIMIT` 回退默认值

**修复**：
1. `app/core/config.py` 新增 `encryption_key` 配置字段
2. 新增 3 个统一入口函数：
   - `get_effective_admin_token()` — 获取生效的管理员 token
   - `get_effective_encryption_key()` — 获取生效的加密种子（回退到 admin_token）
   - `assert_production_config()` — 启动自检
3. `app/middleware/auth.py` 改用 `get_effective_admin_token()`
4. `app/core/crypto.py` 改用 `get_effective_encryption_key()`
5. `app/middleware/rate_limit.py` 改用 `settings.chat_rate_limit`
6. `app/main.py` 在启动时调用 `assert_production_config()`

**额外加固**：`crypto.py` 把单层 SHA256 派生 Fernet key 升级为 `PBKDF2HMAC`（10 万次迭代），防止字典攻击。

### P0-2：asyncio.Lock 失效修复

**根因**：`app/dependencies.py` 的 `get_chat_service` 每次返回 `ChatService()` 新实例，导致 `self._devices_lock = asyncio.Lock()` 每次都是新锁，并发请求间互不阻塞，`device_manager` 的文件读写无保护。

**修复**：
1. 把锁从 `ChatService` 实例下沉到 `device_manager` 单例上
2. 用 `threading.Lock`（因为 device_manager 的文件 I/O 是同步阻塞，`threading.Lock` 更合适）
3. `register_device` / `delete_device` / `get_device` / `get_all_devices` / `update_device_usage` 全部加锁
4. `get_device` / `get_all_devices` 返回拷贝，避免外部修改污染内存
5. 删除死方法：`unregister_device`、`generate_device_code`、`is_device_registered`
6. `ChatService.__init__` 移除 `self._devices_lock`，`_resolve_api_credentials` 不再 `async with`

**测试**：10 线程并发注册全部成功，无重复无丢失。

### P0-5：API Key 脱敏

**根因**：`GET /auth/config` 和 `GET /auth/admin/user-configs` 直接返回 `config.api_key` 明文。管理员一次请求即泄露所有用户的智谱 API Key。

**修复**：
1. 新增 `app/core/redact.py`，提供 `mask_api_key()` 和 `mask_token()` 两个脱敏函数
2. `mask_api_key` 保留前 6 位和后 4 位，中间用 `...` 替代；长度不足 12 位返回 `***`
3. 两个端点的响应都改用 `mask_api_key(config.api_key)`

### S5：validate_key 常量时间比较

**根因**：`api_key_manager.validate_key` 用 `key in keys`，非常量时间比较，有时序攻击风险。

**修复**：改用 `hmac.compare_digest` 逐个比较。空 key 直接返回 False。

### S8：/api/health 加鉴权

**根因**：`/api/health` 探测 LLM 连通性，无鉴权可被滥用做 SSRF 或耗 LLM 配额。

**修复**：加 `Depends(require_admin)`。

### Q1：删除死代码 llm_utils.py

`app/core/llm_utils.py` 全项目零引用，且包含裸 `except:`（第 68 行）。直接删除。

### README.md 重写

- 修复 UTF-16 LE 编码 → UTF-8
- 删除已不存在的 `llm_utils.py` 引用
- `/api/health` 鉴权标注从"无"改为"Admin"
- 新增"安全说明"章节（9 条已落地措施 + 5 条注意事项）
- 新增"部署指南"章节（部署清单 + Nginx 示例 + systemd 示例）
- 新增"开发规范"章节（代码风格 + 提交规范 + 新增技能/端点指引）
- 新增"项目状态"章节（已完成 + 待办路线图）

## 验证

- ✅ 所有修改文件 `py_compile` 语法编译通过
- ✅ `redact` 脱敏函数逻辑测试通过
- ✅ `device_manager` 10 线程并发注册测试通过（无重复无丢失）
- ✅ README UTF-8 编码验证通过

## 未覆盖项（需在后续阶段处理）

| 编号 | 问题 | 阶段 |
| ---- | ---- | ---- |
| P0-3 | 异步端点调同步阻塞 I/O | 第三阶段 |
| P0-4 | Repository 层死代码 | 第二阶段 |
| S3 | JWT secret 回退到 ADMIN_TOKEN | 第三阶段 |
| S6 | `?token=` query 参数传 token | 第三阶段 |
| S12 | 前端 token 存 localStorage | 第三阶段 |
| Q2 | `except Exception:` 静默吞异常 | 第二阶段 |
| T1-T6 | 测试体系重构 | 第四阶段 |
| E1-E3 | 工程化（ruff/mypy/CI/Docker） | 第四阶段 |

详见 `code-review-report.md` 完整路线图。
