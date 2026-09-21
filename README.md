# ErisPulse-Testing

ErisPulse 官方测试工具包（RFC [EPRFC-2026-001](https://github.com/orgs/ErisPulse/discussions/439) 方向三）：
`TestBot` + 事件工厂 + 出站捕获与断言，让模块 / 适配器测试像写普通 pytest 一样简单。

> 单向依赖框架的开发期工具，运行时零介入；不发布到模块商店。

## 特点

- **一行断言回复**：`bot.last_reply.text`、`bot.assert_reply_contains("签到成功")`
- **确定性分发**：`dispatch()` 等待全部处理器落地后再返回，测试里告别 `asyncio.sleep` 猜时间
- **交互可测**：`wait_reply` 对话流用 `reply_as()` 模拟用户回复，自动等待 waiter 注册
- **依赖可换**：`bot.patch_dependency(get_db, fake_value)` 临时替换 `Depends` 依赖
- **生命周期可观测**：`command.matched` / `command.executed` / `adapter.event.blocked` 自动采集
- **pytest 集成**：安装即得 `testbot` fixture（pytest11 entry point）

## 安装

```bash
pip install ErisPulse-Testing
# 或开发安装
pip install -e .
```

## 快速开始

```python
import pytest
from ErisPulse.Core.Event.command import command
from ErisPulse_Testing import TestBot, create_command_event

async def test_daily(make_testbot):
    async with bot_factory(prefix="/") as bot:
        @command("daily", cooldown="1d", cooldown_reply="今天已签到")
        async def daily(event):
            await event.reply("签到成功！")

        await bot.dispatch(create_command_event("daily", user_id="123"))
        assert bot.last_reply.text == "签到成功！"

        await bot.dispatch(create_command_event("daily", user_id="123"))
        bot.assert_reply_contains("今天已签到")          # 第二次命中冷却
        bot.assert_command_executed("daily")             # 生命周期断言
```

`asyncio_mode=auto`（推荐，在 `pyproject.toml` 配 `[tool.pytest.ini_options] asyncio_mode = "auto"`）
或给用例加 `@pytest.mark.asyncio`。

## API 速览

### 事件工厂

| 函数 | 说明 |
|------|------|
| `create_message_event(text, user_id=..., group_id=None, platform=..., bot_id=...)` | 消息事件（uuid 唯一 id，避开框架去重） |
| `create_command_event("roll 3", prefix="/")` | 命令消息（自动加前缀） |
| `create_notice_event(type, ...)` / `create_request_event(type, ...)` / `create_meta_event("connect", ...)` | 通知 / 请求 / meta 事件 |

### TestBot

```python
bot = TestBot(platform="test", bot_id="bot_x", user_id="tester", prefix="/",
              config={"ErisPulse.event.command.case_sensitive": False})
```

| 成员 | 说明 |
|------|------|
| `async with bot:` | 启动（注册 MockAdapter、关事件去重、应用配置）与自动清理 |
| `await bot.dispatch(event, drain=True)` | 分发事件并等待处理器落地；交互首消息传 `drain=False` |
| `await bot.send_message(text, **kw)` | 消息分发快捷方式 |
| `await bot.load_module(名字或类)` / `unload_module(name)` | 加载 / 卸载被测模块 |
| `bot.replies` / `last_reply` / `replies_to(id)` / `clear_replies()` | 出站记录 |
| `assert_replied(contains=None, to=None)` / `assert_not_replied()` / `assert_reply_contains(s)` | 回复断言 |
| `await bot.wait_for_reply(timeout=2)` | 等待异步回复出现 |
| `bot.events("command.executed")` / `last_command` / `blocked_events` | 生命周期观测 |
| `assert_command_executed(name)` | 断言命令成功执行 |
| `bot.patch_dependency(fn, value)` | 临时替换 `Depends` 依赖（with 退出自动还原） |
| `await bot.reply_as(text, user_id=...)` | 模拟 `wait_reply` 用户回复 |
| `bot.adapter.sent` | MockAdapter 原始出站记录（SentMessage：text / segments / target_* / bot_id） |

### pytest fixtures

- `testbot`：function 级标准 TestBot
- `make_testbot(**kwargs)`：自定义参数工厂（`prefix` / `config` / `platform` ...）

## 与 `tests/devs/test_adapter.py` 的分工

本包面向**离线单元 / 集成测试**（不触网、MockAdapter 捕获出站）；
真连适配器平台的冒烟测试请使用框架仓库的 `tests/devs/test_adapter.py` 综合测试框架。

## License

MIT
