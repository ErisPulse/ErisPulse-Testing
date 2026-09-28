<div align="center">

<img src=".github/assets/ErisPulseLogo.png" width="180" alt="ErisPulse-Testing" />

# ErisPulse-Testing

**Official testing toolkit for ErisPulse — TestBot, event factories, reply recording and dispatch-trace assertions.**

<p>
  <a href="https://pypi.org/project/ErisPulse-Testing/"><img src="https://img.shields.io/pypi/v/ErisPulse-Testing?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/ErisPulse-Testing/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/ErisPulse/ErisPulse-Testing"><img src="https://img.shields.io/github/stars/ErisPulse/ErisPulse-Testing?style=for-the-badge&logo=github&color=brightgreen" alt="Stars"></a>
  <a href="https://github.com/ErisPulse/ErisPulse"><img src="https://img.shields.io/badge/Powered_by-ErisPulse-FF6B9D?style=for-the-badge&logo=bookstack&logoColor=white" alt="ErisPulse"></a>
</p>

[English](#english) | [简体中文](#简体中文)

</div>

---

<a id="english"></a>

## English

`TestBot` registers a mock adapter that captures every outbound message, drives the real event dispatch pipeline, and returns the **full decision chain** of each dispatch: command match, scope, ACL, master, permission, cooldown, argument parsing, execution, middleware veto.

### Install

> **Not yet on PyPI** — this package will be published alongside ErisPulse 2.9. Until then, install locally:
>
> ```bash
> pip install -e /path/to/ErisPulse-Testing
> ```
>
> **Version requirements**: core features (TestBot, deterministic dispatch, reply assertions, `wait_reply` simulation, module loading) work with `ErisPulse>=2.8.5`, including the latest stable release on PyPI. Advanced features (dispatch trace, `patch_dependency`, middleware-veto observation, `cooldown=`/`args=` command kwargs) require `ErisPulse>=2.9.0-dev` — they degrade with a clear error on older versions.

### Quick start

```python
import pytest
from ErisPulse.Core.Event.command import command
from ErisPulse_Testing import TestBot, create_command_event

async def test_daily(make_testbot):
    async with make_testbot(prefix="/") as bot:
        @command("daily", cooldown="1d", cooldown_reply="Already claimed today")
        async def daily(event):
            await event.reply("Checked in!")

        await bot.dispatch(create_command_event("daily", user_id="123"))
        assert bot.last_reply.text == "Checked in!"

        await bot.dispatch(create_command_event("daily", user_id="123"))
        bot.assert_reply_contains("Already claimed today")   # cooldown hit
```

### Why didn't my command trigger? (requires EP >= 2.9.0-dev)

Every `dispatch()` returns a `DispatchTrace` — the causal chain of every decision point:

```python
trace = await bot.dispatch(create_command_event("dailyx", user_id="123"))

trace.verdict        # 'no_match'
print(trace.explain())
# ✗ Command "/dailyx" not registered (no command matched the prefix).

trace.assert_no_match()
```

### Highlights

- **Deterministic dispatch** — `dispatch()` waits for all handler tasks before returning
- **Reply assertions** — `bot.last_reply.text`, `assert_replied()`, `assert_reply_contains(...)`
- **Interaction testable** — simulate `wait_reply` flows with `bot.reply_as(...)`
- **Dependencies replaceable** — `bot.patch_dependency(get_db, fake)`
- **Lifecycle observable** — `command.matched` / `command.executed` / `adapter.event.blocked` captured
- **pytest integrated** — `testbot` / `make_testbot` fixtures via pytest11 entry point

See the [简体中文](#简体中文) section below, and the [docs](docs/en/README.md) directory for the detailed API reference and compatibility notes.

---

<a id="简体中文"></a>

## 简体中文

`TestBot` 注册一个捕获全部出站消息的 Mock 适配器，驱动真实的事件分发管线，并返回每次分发的**完整决策链**：命令命中、作用域、ACL、主人、权限、冷却、参数解析、执行结果、中间件否决。

### 安装

> **暂未发布 PyPI**——本包将随 ErisPulse 2.9 正式发包，当前请本地安装：
>
> ```bash
> pip install -e /path/to/ErisPulse-Testing
> ```
>
> **版本要求**：核心功能（TestBot、dispatch 免 sleep drain、出站断言、`wait_reply` 模拟、模块加载）兼容 `ErisPulse>=2.8.5`（含 PyPI 最新稳定版），可直接用于 CI/CD；高级功能（分发决策链、`patch_dependency`、中间件否决观测、命令 `cooldown=` / `args=` 参数）需 `ErisPulse>=2.9.0-dev`，旧版本上自动降级并给出明确报错（`DispatchTrace.available` 为 False）。

### 快速开始

```python
import pytest
from ErisPulse.Core.Event.command import command
from ErisPulse_Testing import TestBot, create_command_event

async def test_daily(make_testbot):
    async with make_testbot(prefix="/") as bot:
        @command("daily", cooldown="1d", cooldown_reply="今天已签到")
        async def daily(event):
            await event.reply("签到成功！")

        await bot.dispatch(create_command_event("daily", user_id="123"))
        assert bot.last_reply.text == "签到成功！"

        await bot.dispatch(create_command_event("daily", user_id="123"))
        bot.assert_reply_contains("今天已签到")   # 第二次命中冷却
```

`async with TestBot()` 启动时注册 MockAdapter、关闭事件去重、应用配置覆写；
退出时自动清理框架全局状态，用例之间互不污染。

### 事件工厂

| 函数 | 说明 |
|------|------|
| `create_message_event(text, user_id=..., group_id=None, ...)` | 消息事件；`group_id` 为空即私聊 |
| `create_command_event("roll 3", prefix="/")` | 命令消息（自动加前缀，已带前缀不重复） |
| `create_notice_event(type, ...)` | 通知事件（如 `friend_add`） |
| `create_request_event(type, ...)` | 请求事件（如好友申请） |
| `create_meta_event("connect", ...)` | meta 事件（connect 可让 Bot 上线） |

所有事件使用 uuid 唯一 `id`，天然避开框架的事件去重。

注意：合成事件**不含平台原始报文**——`event.get_raw()` 返回空 dict。判断
群聊 / 私聊等场景请用 `event.is_group_message()` / `event.get_detail_type()` /
`event.get_group_id()` 等访问器，不要读 raw。

### 分发与交互

```python
trace = await bot.dispatch(event)        # 分发 + 等待处理器落地 + 返回决策链
await bot.dispatch(event, drain=False)   # 交互首消息：不等待（wait_reply 处理器长驻）
await bot.send_message("你好")           # 消息分发快捷方式
await bot.reply_as("18", user_id="u1")   # 模拟 wait_reply 用户回复（自动等 waiter 就绪）
```

`dispatch()` 在 emit 后 gather 全部在途处理器 Task，返回即处理完成。

### 出站断言

```python
bot.replies                # 全部出站（SentMessage 列表）
bot.last_reply.text        # 最近一条回复的文本
bot.replies_to("123")      # 按目标过滤
bot.clear_replies()        # 阶段间隔离断言
bot.assert_replied()                       # 存在出站
bot.assert_replied(contains="签到", to="123")
bot.assert_not_replied()                   # 无任何出站
bot.assert_reply_contains("签到成功")       # 存在包含指定文本的出站
await bot.wait_for_reply(timeout=2)        # 等待异步回复出现
```

`SentMessage` 字段：`text`（首个 text 段）、`segments`（完整消息段）、
`target_type` / `target_id` / `bot_id`（发送上下文）、`has_modifier("at")` 等。

### 模块加载

```python
await bot.load_module("MyModule")   # 已注册的模块名（需框架 sdk.init() 完成 entry-point 发现）
await bot.load_module(MyModule)     # 或 BaseModule 子类（自动 register + load，推荐）
await bot.unload_module("MyModule")
```

`on_load` 内注册的命令 / 事件处理器随模块归属，卸载时自动清理，可直接断言"卸载后命令失效"。
注意：字符串形式**不做 entry-point 扫描**（TestBot 不初始化框架发现流程），仅适用于
模块已注册的场景；测试软依赖模块请直接传类对象（或自行 `module.register` 后传名字）。

### 依赖替换

```python
with bot.patch_dependency(get_session, fake_session) as mock:
    await bot.dispatch(create_command_event("query"))
    assert mock.called
```

替换的是命令注册表中 `Depends(get_session)` 声明引用的函数，with 退出自动还原。

### 配置覆写

```python
bot = TestBot(prefix="//", config={
    "ErisPulse.event.command.case_sensitive": False,
    "MyModule.api_key": "test-key",     # 模块配置（self.cfg 可读）
})
```

经配置内存层注入，命令前缀等随热更新立即生效。两点注意：

1. **落盘**：覆写会随框架的延迟写盘策略（默认约 5 秒）落到 cwd 的
   `config/config.toml`——被测项目仓库请把 `config/` 加入 `.gitignore`；
2. **与模块运行时写回的冲突（已知限制）**：被测模块以整节写回配置
   （`self.cfg = ...`，如订阅列表）与这里的点分覆写并存时，存在 SDK
   ConfigManager 的读写一致性问题——模块整节读取可能看不到覆写值，
   覆写也可能在落盘时被整节写回覆盖（SDK 已在 ErisPulse 2.9.0-dev.1
   修复，2.8.x 仍受影响）。涉及"运行时写回配置"的用例，在 2.8.x 上
   建议在 fixture 里以整节写回方式重置相关配置节。

### 分发决策链（排查"命令为什么没触发"；需 EP>=2.9.0-dev）

```python
trace = await bot.dispatch(create_command_event("dailyx", user_id="123"))

trace.verdict        # executed / rejected / dropped / failed / no_match / passed
trace.explain()      # 逐行因果说明（当前语言）
trace.command        # 命中的命令名（未命中为 None）
trace.steps("cooldown")              # 按阶段过滤判定记录

trace.assert_executed("daily")  # 断言执行（失败时附完整因果链）
trace.assert_rejected()         # 断言被权限类判定拒绝
trace.assert_dropped()          # 断言被静默丢弃（冷却等）
trace.assert_no_match()         # 断言未命中命令
```

判定覆盖：命令文本判定、命令命中（未命中附拼写建议）、作用域、用户 ACL、
主人检查、权限函数、冷却静默丢弃、参数解析、执行结果、中间件否决。
判定点由框架内置（`ErisPulse.Core.Event.trace`），生产环境同样可用
`start_dispatch_trace()` 采集。

### pytest fixtures

- `testbot`：function 级标准 TestBot
- `make_testbot(**kwargs)`：自定义参数工厂（`prefix` / `config` / `platform` / `bot_id` ...）

安装后自动可用（pytest11 entry point）。建议配置 `asyncio_mode = "auto"`。

### 与 `tests/devs/test_adapter.py` 的分工

本包面向**离线单元 / 集成测试**（不触网、MockAdapter 捕获出站）；
真连适配器平台的冒烟测试请使用框架仓库的 `tests/devs/test_adapter.py` 综合测试框架。

### 详细文档

- [docs/zh-CN/api.md](docs/zh-CN/api.md)：TestBot 全量 API 参考
- [docs/zh-CN/compatibility.md](docs/zh-CN/compatibility.md)：版本兼容矩阵、降级行为与已知限制
- [docs/en](docs/en/README.md)：English documentation

## License

MIT
