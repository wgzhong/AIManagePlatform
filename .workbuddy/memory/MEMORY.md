# 项目长期备忘 (MEMORY.md)

## AIManagePlatform 项目

### 技术栈
- **后端**：FastAPI + SQLAlchemy (同步 SQLite) + pydantic-settings
- **AI**：智谱 GLM 系列（GLM-5.1/4.5-Air/4.6V），SSE 流式对话
- **硬件**：ESP32 设备码管理
- **前端**：原生 HTML + CSS + JS（深色玻璃拟态主题）

### 代码评审与重构进度
- **Phase 1** ✅ P0 安全/并发修复（config 双轨、asyncio.Lock、API Key 脱敏、PBKDF2、timing attack、健康检查鉴权）
- **Phase 2** ✅ 架构清理（删除 Repository 死代码、删除 ConfigManager、拆分 auth.py 376→5 文件、统一 DI、修复 8 处静默异常）
- **Phase 3** ✅ FastAPI 最佳实践（拆分 llm_infer.py 巨型类为 3 模块、JWT refresh token、async→def、response_model 覆盖 32/48）
- **Phase 4** ⏳ 工程基线（ruff + mypy + pre-commit + CI + Dockerfile，测试覆盖 50%+）

### 关键架构决策
- **LLM 模块拆分**：`llm_infer.py` 保留为薄封装层（向后兼容），实际逻辑在 `llm_client.py` / `llm_stream.py` / `llm_health.py`
- **JWT 双令牌**：access_token 30min + refresh_token 7d，`/auth/refresh` 端点换发，auth_deps 校验 token type
- **async vs def**：纯同步 DB 操作用 `def`（FastAPI 自动放线程池），SSE/流式/await 才用 `async def`
- **配置入口**：统一用 `settings`（pydantic-settings），禁止 `os.environ.get` 散落

### 文件编码注意
- `README.md` 曾是 UTF-16 LE 编码，已转 UTF-8。写文件时注意编码。
