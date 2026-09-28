# TestBot API Reference

## Event factories

| Function | Description |
|----------|-------------|
| `create_message_event(text, user_id=..., group_id=None, ...)` | Message event; empty `group_id` means private chat |
| `create_command_event("roll 3", prefix="/")` | Command message (prefix added automatically, never doubled) |
| `create_notice_event(type, ...)` | Notice event (e.g. `friend_add`) |
| `create_request_event(type, ...)` | Request event (e.g. friend request) |
| `create_meta_event("connect", ...)` | Meta event (`connect` brings the bot online) |

All events carry a unique uuid `id`, which naturally avoids the framework's event deduplication.

## Lifecycle

```python
async with TestBot(prefix="/", config={...}) as bot:
    ...
```

On startup it registers a MockAdapter (captures all outbound), disables event deduplication, and applies config overrides; on exit it cleans up framework global state, keeping test cases isolated. For pytest, set `asyncio_mode = "auto"` or use the fixtures below.

## Dispatch and interaction

```python
trace = await bot.dispatch(event)          # dispatch, wait for handlers, return a DispatchTrace
await bot.dispatch(event, drain=False)     # first message of an interaction: do not wait
await bot.send_message("你好")             # shortcut for dispatching a message
await bot.reply_as("18", user_id="u1")     # simulate the user's wait_reply answer
reply = await bot.wait_for_reply(timeout=2)  # poll until an async reply appears
```

`dispatch()` gathers all in-flight handler tasks after emit; when it returns, processing is done.

## Outbound assertions

```python
bot.replies                # all outbound messages (list of SentMessage)
bot.last_reply.text        # text of the latest reply
bot.replies_to("123")      # filter by target
bot.clear_replies()        # isolation between phases
bot.assert_replied()                       # at least one outbound message
bot.assert_replied(contains="done", to="123")
bot.assert_not_replied()                   # no outbound messages
bot.assert_reply_contains("done")          # one containing the given text
```

`SentMessage` fields: `text` (first text segment), `segments` (full message segments), `target_type` / `target_id` / `bot_id` (send context), `has_modifier("at")`, etc.

## Lifecycle capture and assertions

```python
bot.events("command.executed")     # captured event payloads
bot.last_command                   # latest command match info
bot.assert_command_executed("roll")  # assert the command executed successfully
bot.blocked_events                 # middleware-vetoed events (requires EP>=2.9.0-dev, see compatibility.md)
```

Captured events: `command.matched` / `command.executed` / `adapter.event.blocked` / `message.sending` / `message.sent`.

## Module loading

```python
await bot.load_module("MyModule")   # registered module name (requires sdk.init() entry-point discovery)
await bot.load_module(MyModule)     # BaseModule subclass (register + load, recommended)
await bot.unload_module("MyModule")
```

Commands / handlers registered inside `on_load` belong to the module and are cleaned up on unload, so "command gone after unload" is directly assertable.

## Adapter under test (DUT)

```python
plat = bot.load_adapter(MyAdapter, platform="dut", config={"token": "t"})
await bot.start_adapter(timeout=5)
await bot.feed_raw({"text": "/ping"})    # converted via the adapter's convert() and dispatched
await bot.stop_adapter()
bot.dut_api_calls                        # call_api spy records (no network)
```

- `config=` is written to the adapter's `_get_config_key()` config section, readable via `self.cfg`
- Loading on the same platform as TestBot replaces the recording adapter; afterwards `bot.replies` gets no new entries — use `bot.dut_api_calls` for outbound assertions
- `feed_raw` requires the adapter to expose `convert(raw)`, otherwise it raises `AttributeError`

## Dependency override (requires EP>=2.9.0-dev)

```python
with bot.patch_dependency(get_session, fake_session) as mock:
    await bot.dispatch(create_command_event("query"))
    assert mock.called
```

Swaps the function referenced by `Depends(get_session)` declarations in the command registry; restored automatically on exit.

## Dispatch trace (requires EP>=2.9.0-dev)

```python
trace = await bot.dispatch(create_command_event("dailyx", user_id="123"))

trace.verdict        # executed / rejected / dropped / failed / no_match / passed
trace.explain()      # human-readable causal chain (current language)
trace.command        # matched command name (None if none)
trace.steps("cooldown")              # filter records by stage
trace.available                      # whether the trace data source is available

trace.assert_executed("daily")  # assert execution (with the full chain on failure)
trace.assert_rejected()         # assert rejection by a permission-type check
trace.assert_dropped()          # assert silent drop (cooldown etc.)
trace.assert_no_match()         # assert no command matched
```

Covered decision points: command text check, command match (with spelling suggestion on miss), scope, user ACL, master check, permission function, cooldown silent drop, argument parsing, execution result, middleware veto. The trace is provided by the framework itself (`ErisPulse.Core.Event.trace`) and can also be collected in production via `start_dispatch_trace()`.

## pytest fixtures

- `testbot`: function-scoped standard TestBot (platform=`test`, prefix `/`)
- `make_testbot(**kwargs)`: parameterized factory (`prefix` / `config` / `platform` / `bot_id` ...)

Both are available automatically after installation (pytest11 entry point).
