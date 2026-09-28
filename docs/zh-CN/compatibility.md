# 版本兼容与已知限制

## 版本要求

| 能力 | 最低 ErisPulse 版本 |
|------|---------------------|
| TestBot 生命周期、dispatch 免等待分发、出站断言、`wait_reply` 模拟、模块加载、被测适配器（DUT） | 2.8.5（含 PyPI 稳定版） |
| 分发决策链（`DispatchTrace` / `trace.assert_*`） | 2.9.0-dev |
| `patch_dependency`（Depends 依赖替换） | 2.9.0-dev |
| 中间件否决观测（`bot.blocked_events`） | 2.9.0-dev |
| 命令装饰器 `args=` / `cooldown=` 等治理参数 | 2.9.0-dev |

## 降级行为

高级特性在旧版本 SDK 上经特性探测（`ErisPulse_Testing._compat`）自动降级，不抛含混异常：

- `dispatch()` 照常分发并等待处理器落地，返回的 `DispatchTrace` 形状完整，但 `records` 恒空、`verdict` 恒为 `"unknown"`、`available` 为 `False`
- `trace.assert_*` 与 `bot.patch_dependency` 抛 `RuntimeError`，消息含所需版本与当前安装版本
- `bot.blocked_events` 恒为空（2.8.x 中间件无 False 否决契约）

本仓库 CI 以双版本腿持续验证兼容性：PyPI `ErisPulse==2.8.6` 与 `ErisPulse/ErisPulse` 仓库 `Develop/v2` 分支源码各跑一遍完整测试。

## 已知限制

### 配置覆写与模块整节写回的冲突

被测模块以整节写回配置（`self.cfg = ...`，如订阅列表）与 `TestBot(config={...})` 的点分覆写并存时，存在 SDK ConfigManager 的读写一致性问题——模块整节读取可能看不到覆写值，覆写也可能在落盘时被整节写回覆盖。

- 已在 ErisPulse 2.9.0-dev.1 修复（BUG-039），2.8.x 仍受影响
- 2.8.x 绕行：在 fixture 里以整节写回方式重置相关配置节

```python
cfg = daily.cfg
cfg.push_targets = []
daily.cfg = cfg   # 整节 dirty 写在 getConfig 精确命中，读写路径都生效
```

### 合成事件不含平台原始报文

`event.get_raw()` 返回空 dict。判断群聊 / 私聊用 `event.is_group_message()` / `event.get_detail_type()` / `event.get_group_id()` 等访问器，不要读 raw。

### `load_module("名字")` 不做 entry-point 扫描

字符串形式仅适用于模块已注册（框架 `sdk.init()` 完成 entry-point 发现）的场景；测试软依赖模块请直接传类对象。

### 测试运行在 cwd 生成 `config/`

框架单例按进程 cwd 创建 `config/config.toml` 与 `config.db`（含测试注入的覆写值），被测仓库请将 `config/` 加入 `.gitignore`。
