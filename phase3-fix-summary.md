# 第三阶段修复总结 — FastAPI 最佳实践

> **阶段目标**：按 FastAPI 官方推荐实践优化路由层与 LLM 推理模块，提升类型安全、并发性能与可维护性。
> **执行时间**：2026-06-25
> **验证方式**：`py_compile` 语法检查 + AST/字符串结构化验证（无运行时依赖可用）

---

## F0: 修复 llm_infer.py 运行时 bug

**问题**：`app/core/llm_infer.py` 第 44 行
```python
self._debug_mode = config._settings.llm_debug  # ❌ config 未定义
```
`config` 既未 import 也未定义，一旦 `LLMInfer.__init__` 被调用即抛 `NameError`。这是个隐藏的运行时炸弹——因为模块级 `llm_infer = LLMInfer()` 在 import 时就会触发。

**修复**：改为 `settings.llm_debug`（与其他地方一致）。

---

## F4: 拆分 llm_infer.py 巨型类

**问题**：原 `llm_infer.py` 503 行，`LLMInfer` 类承担 5 项不同职责：
1. HTTP 客户端管理（连接池/HTTP2/SSL）
2. 连接预热（warmup）
3. 心跳保活（heartbeat）
4. 消息截断 + JSON 序列化
5. SSE 流式请求 + 重试
6. 健康检查

违反单一职责原则，难以测试与维护。

**拆分方案**：

| 新模块 | 职责 | 核心导出 |
|--------|------|----------|
| `app/core/llm_client.py` | HTTP 客户端管理、预热、心跳 | `LLMHttpClient` 类 + `llm_client` 单例 |
| `app/core/llm_stream.py` | 流式请求、SSE 解析、重试 | `LLMStreamer` 类 + `llm_streamer` 单例 + `stream_chat_request()` |
| `app/core/llm_health.py` | 健康检查 | `check_health()` |
| `app/core/llm_infer.py` | **薄封装层**，保留向后兼容 | `LLMInfer` 类 + `llm_infer` 单例 + `stream_chat_request()` |

**向后兼容**：`llm_infer.py` 保留 `LLMInfer` 类与 `llm_infer` 全局实例，内部委托给三个子模块。所有现有调用方（`chat_service.py`、`main.py`、`stats.py`）**无需任何改动**。

模块常量（`LIMITS`、`TIMEOUT`、`HEARTBEAT_INTERVAL`）也从类属性迁移到 `llm_client.py` 模块级。

---

## F2: 实现 JWT Refresh Token 机制

**问题**：原登录只签发 access_token（30 分钟有效期），用户每 30 分钟必须重新登录，体验差。

**方案**：双令牌机制
- **access_token**：短期（30 分钟），用于 API 鉴权
- **refresh_token**：长期（7 天），仅用于换取新 access_token

### 新增/修改

**`app/services/user_service.py`**：
- 新增常量 `REFRESH_TOKEN_EXPIRE_DAYS = 7`、`TOKEN_TYPE_ACCESS = "access"`、`TOKEN_TYPE_REFRESH = "refresh"`
- 新增 `create_refresh_token(data, expires_delta)` 函数
- 新增 `decode_token(token)` 通用解码函数
- 新增 `verify_refresh_token(token)` 验证 refresh_token 并返回 sub（邮箱）
- `create_access_token` 现在在 payload 中注入 `"type": "access"`

**`app/api/auth_deps.py`**：
- `get_current_user` 增加 token type 校验：`payload.get("type") != "access"` 则拒绝
- 防止 refresh_token 被误当作 access_token 使用

**`app/api/auth.py`**：
- `/auth/login` 响应新增 `refresh_token` 字段
- **新增** `POST /auth/refresh` 端点：接收 `refresh_token`，验证后签发新 `access_token`

**`app/schemas/auth.py`**（新文件）：
- `TokenResponse` 含 `access_token` + `refresh_token` + `user`
- `RefreshTokenRequest` / `RefreshTokenResponse`

### 使用流程

```bash
# 1. 登录，拿到两个 token
POST /auth/login
→ { "access_token": "xxx", "refresh_token": "yyy", "token_type": "bearer", "user": {...} }

# 2. 用 access_token 调 API（30 分钟有效）
GET /auth/me
Headers: Authorization: Bearer xxx

# 3. access_token 过期后，用 refresh_token 换新的
POST /auth/refresh
Body: { "refresh_token": "yyy" }
→ { "access_token": "zzz", "token_type": "bearer" }

# 4. 继续用新 access_token 调 API
```

---

## F1: async 路由改 def（同步 DB 操作）

**问题**：FastAPI 中 `async def` 路由运行在事件循环主线程上。如果内部调用同步阻塞 I/O（如 SQLAlchemy 同步 Session），会阻塞整个事件循环，导致所有并发请求被串行化。

**官方建议**：纯同步 I/O 的路由用 `def`，FastAPI 会自动放到线程池执行；真正用到 `await` 的路由才用 `async def`。

### 改动清单

| 文件 | 改 async → def 的端点 | 保持 async 的端点 |
|------|----------------------|-------------------|
| `auth.py` | register, login, refresh, me, logout | — |
| `user_config.py` | get_config, update_config | — |
| `user_history.py` | get_history, clear_history, get_user_stats | — |
| `admin_users.py` | get_users, get_single_user, update_single_user, delete_single_user, get_all_user_configs | — |
| `devices.py` | register_device, list_devices, delete_device, get_device | — |
| `keys.py` | generate_new_api_key, list_api_keys, delete_api_key, validate_api_key | — |
| `skills.py` | get_skills, get_skills_config, update_skill_config, get_skill_system_prompt, save_skill_system_prompt, get_skill_file_path, create_custom_skill | — |
| `reminders.py` | get_reminders, get_reminder, set_reminder, cancel_reminder | **notifications**（SSE 流式，需 await 订阅） |
| `stats.py` | get_stats | **health_check**（await LLM 健康检查） |
| `history.py` | get_chat_history, clear_chat_history | — |
| `mood.py` | get_mood_prompt_api | — |
| `pages.py` | index, home_page, login_page, chat_page, devices_page, skills_page | — |
| `chat.py` | — | **chat**（StreamingResponse 流式响应） |

---

## F3: 为所有路由添加 response_model

**问题**：原路由返回裸 dict，OpenAPI 文档无法描述响应结构，也无法自动校验/过滤响应字段。

### 新增 schemas

| 文件 | 模型 |
|------|------|
| `app/schemas/auth.py`（新） | `UserCreate`, `UserPublic`, `RegisterResponse`, `TokenResponse`, `RefreshTokenRequest`, `RefreshTokenResponse`, `MessageResponse` |
| `app/schemas/user.py`（新） | `UserConfigResponse`, `UserConfigUpdate`, `UserConfigUpdateResponse`, `ChatHistoryItem`, `UserStatsResponse` |
| `app/schemas/admin.py`（新） | `UserListItem`, `UserListResponse`, `UserUpdateResponse`, `UserConfigItem`, `AllUserConfigsResponse` |

### response_model 覆盖率

**32 / 48 路由** 添加了 `response_model`。

未添加的 16 个路由属于以下情况（不适合强类型 response_model）：
- SSE 流式端点（`/chat`、`/api/notifications`）—— 返回 `StreamingResponse`
- 静态页面端点（`/`、`/home`、`/login` 等）—— 返回 `FileResponse`
- 返回动态 dict 结构的端点（`/api/skills`、`/api/skills/config`、`/api/skills/custom`、`/api/reminders` POST）—— 结构不固定

---

## 修改文件清单

### 新增文件（5 个）
- `app/core/llm_client.py` — LLM HTTP 客户端管理
- `app/core/llm_stream.py` — LLM 流式请求处理
- `app/core/llm_health.py` — LLM 健康检查
- `app/schemas/auth.py` — 认证相关响应模型
- `app/schemas/user.py` — 用户配置/历史响应模型
- `app/schemas/admin.py` — 管理员用户管理响应模型

### 修改文件（14 个）
- `app/core/llm_infer.py` — 重写为薄封装层（503→139 行），修复 F0 bug
- `app/services/user_service.py` — 新增 refresh token 相关函数
- `app/schemas/__init__.py` — 导出新 schemas
- `app/api/auth.py` — 新增 /refresh 端点，async→def，补 response_model
- `app/api/auth_deps.py` — 增加 token type 校验
- `app/api/user_config.py` — async→def，补 response_model
- `app/api/user_history.py` — async→def，补 response_model
- `app/api/admin_users.py` — async→def，补 response_model
- `app/api/devices.py` — async→def，补 response_model
- `app/api/keys.py` — async→def，补 response_model
- `app/api/stats.py` — 补 response_model（health 保持 async）
- `app/api/skills.py` — async→def，补 response_model
- `app/api/reminders.py` — DB 操作 async→def（notifications 保持 async），补 response_model
- `app/api/history.py` — async→def，补 response_model
- `app/api/mood.py` — async→def
- `app/api/pages.py` — async→def

---

## 验证结果

```
PASS: app/core/llm_client.py
PASS: app/core/llm_stream.py
PASS: app/core/llm_health.py
PASS: app/core/llm_infer.py
PASS: app/api/chat.py keeps async
PASS: app/api/reminders.py keeps async
PASS: app/api/stats.py keeps async
PASS: app/api/auth.py all routes are def
PASS: app/api/user_config.py all routes are def
PASS: app/api/user_history.py all routes are def
PASS: app/api/admin_users.py all routes are def
PASS: app/api/devices.py all routes are def
PASS: app/api/keys.py all routes are def
PASS: app/api/skills.py all routes are def
PASS: app/api/history.py all routes are def
PASS: app/api/mood.py all routes are def
PASS: app/api/pages.py all routes are def
PASS: /auth/refresh endpoint exists
PASS: auth_deps validates token type
INFO: 32/48 routes have response_model
PASS: F0 bug fixed (no more config._settings)

=== ALL VALIDATIONS PASSED ===
```

所有 23 个修改/新增文件均通过 `py_compile` 语法检查。
