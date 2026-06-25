# 第二阶段架构清理总结

> 完成时间：2026-06-25
> 对应报告：`code-review-report.md` 第二阶段（架构清理）

## 修复清单

| 编号 | 问题 | 修改方式 | 状态 |
| ---- | ---- | ---- | ---- |
| **P0-4** | Repository 层 195 行 100% 死代码 | 删除整个 `app/repositories/` 目录 | ✅ |
| **A4** | `ConfigManager` 包装类冗余 | 删除 `ConfigManager` 类，全项目改用 `settings` | ✅ |
| **A9** | `chat_history.py` 已弃用但仍在仓库 | 删除文件 + 删除相关配置项 | ✅ |
| **A10** | `llm_utils.py` 死代码 | 第一阶段已删除 | ✅ |
| **A11** | `main.py` 未使用的 `threading`/`os` 导入 | 删除 | ✅ |
| **A6** | `auth.py` 单文件 376 行 14 端点 | 拆分为 5 个文件 | ✅ |
| **A2** | 路由内重复定义 `get_xxx_service` | 统一用 `app/dependencies.py` | ✅ |
| **F7** | `get_current_user` 写在路由层 | 抽离到 `app/api/auth_deps.py` | ✅ |
| **Q2** | `base_skill.py` 6 处静默吞异常 | 改为 `logger.exception` | ✅ |
| **Q2** | `skill_service.py` / `reminder_manager.py` 静默吞异常 | 改为 `logger.exception` | ✅ |
| **Q14** | `stats.py` 用 f-string 而非 `%s` | 改为 `%s` 占位符 | ✅ |

## 详细修改说明

### P0-4：删除 Repository 死代码

**根因**：`app/repositories/` 下 3 个文件（`base.py`、`user_repo.py`、`chat_history_repo.py`）定义了完整的 Repository 模式 CRUD，但全项目 `from app.repositories` 零引用。实际数据访问散落在 `services/*.py` 和 `api/*.py` 里直接用 `db.query`。保留死代码会误导新人。

**修复**：`rm -rf app/repositories`。

### A4：删除 ConfigManager 包装类

**根因**：`ConfigManager` 把 `settings.xxx` 包装成 `config.XXX` 大写形式，无额外逻辑，纯粹是历史包袱。两套访问方式（`config.API_KEYS` vs `settings.api_keys`）让新人困惑，也增加了维护成本。

**修复**：
1. 从 `config.py` 删除整个 `ConfigManager` 类和 `config = ConfigManager(settings)` 实例
2. 全项目 8 个文件的 `config.XXX` 替换为 `settings.xxx`：

| 旧写法 | 新写法 |
| ------ | ------ |
| `config.API_KEYS` | `settings.api_keys` |
| `config.DEFAULT_URL` | `settings.zhipu_api_url` |
| `config.DEFAULT_MODEL` | `settings.llm_default_model` |
| `config.LLM_VERIFY_SSL` | `settings.llm_verify_ssl` |
| `config.APP_PORT` | `settings.app_port` |
| `config.API_KEYS_FILE` | `settings.api_keys_file` |
| `config.DEVICES_FILE` | `settings.devices_file` |
| `config.STATS_FILE` | `settings.stats_file` |
| `config.BASE_DIR` | `settings.base_dir` |

涉及文件：`api_keys.py`、`devices.py`、`stats.py`、`llm_infer.py`、`chat_service.py`、`main.py`、`pages.py`。

3. `SYSTEM_START_TIME` 保留为模块级变量（原由 ConfigManager 持有）。

### A9：删除已弃用的 chat_history.py

**根因**：`app/core/chat_history.py` 整个文件标注"已弃用"，聊天历史已迁移到 SQLite。但 `config.py` 还保留 `chat_history_file` 和 `max_chat_history_size` 配置项。

**修复**：删除 `chat_history.py` 文件 + 从 `Settings` 类删除两个配置项。

### A6：拆分 auth.py

**根因**：`app/api/auth.py` 单文件 376 行，含注册/登录/me/配置/历史/统计/管理员用户管理 7 类职责 14 个端点，违反单一职责原则。

**修复**：拆分为 5 个文件：

| 新文件 | 职责 | 端点数 |
| ------ | ---- | ------ |
| `app/api/auth.py` | 注册、登录、me、logout | 4 |
| `app/api/auth_deps.py` | 共享依赖：`get_current_user`、`require_superuser` | 0（依赖） |
| `app/api/user_config.py` | 用户配置 GET/PUT | 2 |
| `app/api/user_history.py` | 聊天历史、用户统计 | 3 |
| `app/api/admin_users.py` | 管理员用户管理 + 用户配置查看 | 5 |

每个文件聚焦单一职责，最大文件 100 行，便于维护。

### A2 + F7：统一依赖注入 + 抽离认证依赖

**根因**：
1. `devices.py`/`keys.py`/`skills.py`/`reminders.py` 各自重复定义 `get_xxx_service` 工厂函数，与 `app/dependencies.py` 重复
2. `get_current_user` 把 JWT 解析逻辑写在 `auth.py` 路由层，`chat.py` 只能 `from app.api.auth import get_current_user`，造成路由间耦合

**修复**：
1. 4 个路由文件删除本地 `get_xxx_service` 定义，改用 `from app.dependencies import get_xxx_service`
2. 新建 `app/api/auth_deps.py`，把 `get_current_user` 和新增的 `require_superuser` 抽离出来
3. `chat.py` 改为 `from app.api.auth_deps import get_current_user`
4. 管理员端点统一用 `Depends(require_superuser)` 替代手写 `if not current_user.is_superuser` 判断

### Q2：修复静默吞异常

**根因**：`base_skill.py` 有 6 处 `except Exception: pass` 或 `except Exception: return`，完全吞掉异常无日志。`skill_service.py` 和 `reminder_manager.py` 各有 1 处。出问题时无法定位。

**修复**：全部改为 `logger.exception("...")` 记录完整栈，再执行原有的回退逻辑（return None/False/默认值）。

| 文件 | 修复处数 |
| ---- | -------- |
| `app/skills/base_skill.py` | 6 |
| `app/services/skill_service.py` | 1 |
| `app/core/reminder_manager.py` | 1 |

### Q14：stats.py 日志格式

`stats.py:65` 的 `logger.warning(f"统计落盘失败: {e}")` 改为 `logger.warning("统计落盘失败: %s", e)`，避免 f-string 在日志热路径上的性能开销。

## 删除的文件清单

```
app/repositories/__init__.py      (死代码)
app/repositories/base.py          (死代码)
app/repositories/user_repo.py     (死代码)
app/repositories/chat_history_repo.py (死代码)
app/core/chat_history.py          (已弃用)
```

## 新增的文件清单

```
app/api/auth_deps.py              (认证共享依赖)
app/api/user_config.py            (用户配置路由)
app/api/user_history.py           (用户历史与统计路由)
app/api/admin_users.py            (管理员用户管理路由)
```

## 修改的文件清单

```
app/core/config.py          (删除 ConfigManager，删除 chat_history 配置)
app/core/api_keys.py        (config → settings)
app/core/devices.py         (config → settings)
app/core/stats.py           (config → settings + 日志格式)
app/core/llm_infer.py       (config → settings，5 处)
app/core/reminder_manager.py(静默 except → logger.exception)
app/api/auth.py             (拆分，仅保留注册/登录/me/logout)
app/api/chat.py             (get_current_user 改从 auth_deps 导入)
app/api/devices.py          (删除本地 get_device_service)
app/api/keys.py             (删除本地 get_api_key_service)
app/api/skills.py           (删除本地 get_skill_service)
app/api/reminders.py        (删除本地 get_reminder_service)
app/api/pages.py            (config.BASE_DIR → settings.base_dir)
app/services/chat_service.py(config → settings)
app/services/skill_service.py(静默 except → logger.exception)
app/skills/base_skill.py    (6 处静默 except → logger.exception)
app/main.py                 (注册 3 个新路由 + 删除未使用导入)
README.md                   (更新项目结构 + 项目状态)
```

## 验证

- ✅ 所有 27 个修改/新增文件 `py_compile` 语法编译通过
- ✅ `app/repositories/` 目录已删除（`find_spec` 返回 None）
- ✅ `app/core/chat_history.py` 已删除
- ✅ `ConfigManager` 类和 `config` 实例已删除
- ✅ `chat_history_file` / `max_chat_history_size` 配置项已删除
- ✅ `SYSTEM_START_TIME` 保留为模块级变量
- ✅ `auth.py` 已拆分为 5 个文件
- ✅ 4 个路由文件不再定义 `get_xxx_service`
- ✅ `get_current_user` / `require_superuser` 已抽离到 `auth_deps.py`
- ✅ `chat.py` 改用 `auth_deps.get_current_user`
- ✅ `base_skill.py` 6 处静默 except 全部修复
- ✅ `reminder_manager.py` / `skill_service.py` 静默 except 已修复
- ✅ `main.py` 注册了 3 个新路由
- ✅ 全项目无 `config.XXX` 残留引用

## 架构改进效果

### 拆分前后对比

| 指标 | 拆分前 | 拆分后 |
| ---- | ------ | ------ |
| `auth.py` 行数 | 376 | 110（最大文件） |
| `auth.py` 端点数 | 14 | 4（聚焦认证） |
| 路由文件数 | 10 | 14（更细粒度） |
| 配置访问方式 | 2 种（`config` + `settings`） | 1 种（`settings`） |
| 死代码文件 | 5 个 | 0 |
| 静默吞异常 | 8 处 | 0 |

### 团队收益

1. **新人上手更快**：`auth.py` 不再是 376 行的巨石，按职责找文件即可
2. **配置不再困惑**：只有 `settings` 一个入口，`config.XXX` 大写形式彻底消失
3. **调试更高效**：所有异常都有栈日志，不再"莫名其妙返回 None"
4. **测试更友好**：`get_current_user` 是独立依赖，测试时可直接 override

## 未覆盖项（需在后续阶段处理）

| 编号 | 问题 | 阶段 |
| ---- | ---- | ---- |
| P0-3 | 异步端点调同步阻塞 I/O | 第三阶段 |
| A7 | `llm_infer.py` 上帝类 545 行 | 第三阶段 |
| A8 | 用户统计双写（SQLite + JSON） | 第三阶段 |
| F4 | JWT 无 refresh token / blacklist | 第三阶段 |
| F8 | 端点缺 `response_model` | 第三阶段 |
| T1-T6 | 测试体系重构 | 第四阶段 |
| E1-E3 | 工程化（ruff/mypy/CI/Docker） | 第四阶段 |

详见 `code-review-report.md` 完整路线图。
