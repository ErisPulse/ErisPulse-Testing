# TestBot API 参考

## 事件工厂

| 函数 | 说明 |
|------|------|
| `create_message_event(text, user_id=..., group_id=None, ...)` | 消息事件；`group_id` 为空即私聊 |
| `create_command_event("roll 3", prefix="/")` | 命令消息（自动加前缀，已带前缀不重复） |
| `create_notice_event(type, ...)` | 通知事件（如 `friend_add`） |
| `create_request_event(type, ...)` | 请求事件（如好友申请） |
| `create_meta_event("connect", ...)` | meta 事件（connect 可让 Bot 上线） |

所有事件使用 uuid 唯一 `id`，天然避开框架的事件去重。

## 生命周期

```python
async with TestBot(prefix="/", config={...}) as bot:
    ...
```

启动时注册 MockAdapter（捕获全部出站）、关闭事件去重、应用配置覆写；退出时自动清理框架全局状态，用例之间互不污染。pytest 项目建议配置 `asyncio_mode = "auto"`，或使用下文 fixtures。

## 分发与交互

```python
trace = await bot.dispatch(event)          # 分发并等待处理器落地，返回 DispatchTrace
await bot.dispatch(event, drain=False)     # 交互首消息：不等待（wait_reply 处理器长驻）
await bot.send_message("你好")             # 消息分发快捷方式
await bot.reply_as("18", user_id="u1")     # 模拟 wait_reply 用户回复（自动等 waiter 就绪）
reply = await bot.wait_for_reply(timeout=2)  # 轮询等待异步回复出现
```

`dispatch()` 在 emit 后 gather 全部在途处理器 Task，返回即处理完成。

## 出站断言

```python
bot.replies                # 全部出站（SentMessage 列表）
bot.last_reply.text        # 最近一条回复的文本
bot.replies_to("123")      # 按目标过滤
bot.clear_replies()        # 阶段间隔离断言
bot.assert_replied()                       # 存在出站
bot.assert_replied(contains="签到", to="123")
bot.assert_not_replied()                   # 无任何出站
bot.assert_reply_contains("签到成功")       # 存在包含指定文本的出站
```

`SentMessage` 字段：`text`（首个 text 段）、`segments`（完整消息段）、`target_type` / `target_id` / `bot_id`（发送上下文）、`has_modifier("at")` 等。

## 生命周期采集与断言

```python
bot.events("command.executed")     # 已采集的事件 data 列表
bot.last_command                   # 最近一次命令匹配信息
bot.assert_command_executed("roll")  # 断言命令成功执行
bot.blocked_events                 # 被中间件否决的事件（需 EP>=2.9.0-dev，见 compatibility.md）
```

采集的事件：`command.matched` / `command.executed` / `adapter.event.blocked` / `message.sending` / `message.sent`。

## 模块加载

```python
await bot.load_module("MyModule")   # 已注册的模块名（需框架 sdk.init() 完成 entry-point 发现）
await bot.load_module(MyModule)     # BaseModule 子类（自动 register + load，推荐）
await bot.unload_module("MyModule")
```

`on_load` 内注册的命令 / 事件处理器随模块归属，卸载时自动清理，可直接断言"卸载后命令失效"。

## 被测适配器（DUT）

```python
plat = bot.load_adapter(MyAdapter, platform="dut", config={"token": "t"})
await bot.start_adapter(timeout=5)
await bot.feed_raw({"text": "/ping"})    # 经适配器 convert() 转换后分发
await bot.stop_adapter()
bot.dut_api_calls                        # call_api 间谍记录（不触网）
```

- `config=` 写入适配器 `_get_config_key()` 对应配置节，适配器 `self.cfg` 可读
- `load_adapter` 平台名与 TestBot 相同时会替换记录型适配器，此后 `bot.replies` 不再有新记录，出站断言改用 `bot.dut_api_calls`
- `feed_raw` 要求适配器暴露 `convert(raw)` 入口，否则抛 `AttributeError`

## 依赖替换（需 EP>=2.9.0-dev）

```python
with bot.patch_dependency(get_session, fake_session) as mock:
    await bot.dispatch(create_command_event("query"))
    assert mock.called
```

替换命令注册表中 `Depends(get_session)` 声明引用的函数，with 退出自动还原。

## 分发决策链（需 EP>=2.9.0-dev）

```python
trace = await bot.dispatch(create_command_event("dailyx", user_id="123"))

trace.verdict        # executed / rejected / dropped / failed / no_match / passed
trace.explain()      # 逐行因果说明（当前语言）
trace.command        # 命中的命令名（未命中为 None）
trace.steps("cooldown")              # 按阶段过滤判定记录
trace.available                      # 决策链数据源是否可用

trace.assert_executed("daily")  # 断言执行（失败时附完整因果链）
trace.assert_rejected()         # 断言被权限类判定拒绝
trace.assert_dropped()          # 断言被静默丢弃（冷却等）
trace.assert_no_match()         # 断言未命中命令
```

判定覆盖：命令文本判定、命令命中（未命中附拼写建议）、作用域、用户 ACL、主人检查、权限函数、冷却静默丢弃、参数解析、执行结果、中间件否决。判定点由框架内置（`ErisPulse.Core.Event.trace`），生产环境同样可用 `start_dispatch_trace()` 采集。

## pytest fixtures

- `testbot`：function 级标准 TestBot（platform=`test`、前缀 `/`）
- `make_testbot(**kwargs)`：自定义参数工厂（`prefix` / `config` / `platform` / `bot_id` ...）

安装后自动可用（pytest11 entry point）。
