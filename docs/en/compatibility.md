# Compatibility and Known Limitations

## Version requirements

| Capability | Minimum ErisPulse version |
|------------|---------------------------|
| TestBot lifecycle, dispatch without sleeps, outbound assertions, `wait_reply` simulation, module loading, adapter under test (DUT) | 2.8.5 (incl. PyPI stable release) |
| Dispatch trace (`DispatchTrace` / `trace.assert_*`) | 2.9.0-dev |
| `patch_dependency` (Depends override) | 2.9.0-dev |
| Middleware-veto observation (`bot.blocked_events`) | 2.9.0-dev |
| Command decorator governance kwargs (`args=` / `cooldown=` / ...) | 2.9.0-dev |

## Degradation behavior

Advanced features are probed at runtime (`ErisPulse_Testing._compat`) and degrade cleanly on older SDK versions instead of failing with obscure errors:

- `dispatch()` still dispatches and waits for handlers; the returned `DispatchTrace` keeps its shape, but `records` stays empty, `verdict` is `"unknown"`, and `available` is `False`
- `trace.assert_*` and `bot.patch_dependency` raise `RuntimeError` with the required and the currently installed version in the message
- `bot.blocked_events` stays empty (2.8.x middleware has no `False`-veto contract)

CI runs the full test suite against two versions to keep this promise: PyPI `ErisPulse==2.8.6` and the `Develop/v2` branch of the `ErisPulse/ErisPulse` repository.

## Known limitations

### Config overrides vs. module runtime config writes

When the module under test writes back its whole config section (`self.cfg = ...`, e.g. a subscription list) while `TestBot(config={...})` injects dotted overrides, the SDK ConfigManager has a read/write consistency issue — the module's whole-section reads may not see the override, and the override may be lost on disk when the section write lands.

- Fixed in ErisPulse 2.9.0-dev.1 (BUG-039); 2.8.x is still affected
- Workaround on 2.8.x: reset the relevant config section via a whole-section write in the fixture

```python
cfg = daily.cfg
cfg.push_targets = []
daily.cfg = cfg   # section dirty writes hit getConfig exactly and always win
```

### Synthetic events carry no platform raw payload

`event.get_raw()` returns an empty dict. Use `event.is_group_message()` / `event.get_detail_type()` / `event.get_group_id()` accessors to tell group from private chats instead of reading raw.

### `load_module("name")` performs no entry-point scan

The string form only works for already-registered modules (after the framework's `sdk.init()` entry-point discovery); for soft-dependency modules in tests, pass the class object directly.

### Tests create `config/` in the working directory

Framework singletons create `config/config.toml` and `config.db` under the process cwd (including injected override values); add `config/` to the tested repository's `.gitignore`.
