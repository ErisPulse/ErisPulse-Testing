"""
TestBot —— ErisPulse 模块 / 命令 / 事件的测试驱动主体

按 RFC EPRFC-2026-001 方向三实现：注入用户消息 → 模块/命令响应 →
断言回复与生命周期事件，配合 pytest 使用。单向依赖 ErisPulse，
全部走公开挂接点（adapter.emit / adapter.register / module.register /
module.load / lifecycle），不改动框架核心。

{!--< tips >!--}
1. 推荐 ``async with TestBot() as bot:`` 使用，退出时自动清理全局状态
2. dispatch() 会等待全部事件处理器 Task 落地后再返回——断言无需 sleep
3. 出站消息由 MockAdapter 记录，replies / last_reply 直接断言
{!--< /tips >!--}
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, Mock

from .events import (
    DEFAULT_BOT_ID,
    DEFAULT_PLATFORM,
    DEFAULT_USER_ID,
    create_message_event,
)
from .mock_adapter import MockAdapter
from .replies import SentMessage
from .trace import DispatchTrace

# TestBot 启动时采集的生命周期事件（断言命令执行 / 中间件否决等）
_OBSERVED_LIFECYCLE_EVENTS = (
    "command.matched",
    "command.executed",
    "adapter.event.blocked",
    "message.sending",
    "message.sent",
)


class TestBot:
    """
    ErisPulse 测试机器人

    注册 MockAdapter 捕获出站、驱动 adapter.emit 分发合成事件、加载被测
    模块，并提供回复 / 生命周期断言面。

    :param platform: MockAdapter 平台名（事件工厂缺省使用同名平台）
    :param bot_id: Bot 账号 ID
    :param prefix: 命令前缀（经配置内存层注入，命令热更新自动生效）
    :param config: 附加配置覆写（点分键 → 值，setConfig 内存层不落盘）
    """

    def __init__(
        self,
        *,
        platform: str = DEFAULT_PLATFORM,
        bot_id: str = DEFAULT_BOT_ID,
        user_id: str = DEFAULT_USER_ID,
        prefix: str = "/",
        config: dict[str, Any] | None = None,
    ):
        self.platform = platform
        self.bot_id = bot_id
        self.user_id = user_id
        self.prefix = prefix
        self._config = dict(config or {})
        self._adapter: MockAdapter | None = None
        self._loaded_modules: list[str] = []
        self._dedupe_prev: bool | None = None
        self._lifecycle_hooks: list[tuple[str, Any]] = []
        self._observed: dict[str, list[dict[str, Any]]] = {name: [] for name in _OBSERVED_LIFECYCLE_EVENTS}
        self._traces: list[DispatchTrace] = []
        self._started = False

    # ==================== 生命周期 ====================

    async def startup(self) -> TestBot:
        """
        启动测试环境：注册 MockAdapter、关闭事件去重、应用配置覆写、挂生命周期采集器

        :return: self（支持链式 / async with）
        """
        from ErisPulse import adapter, config, lifecycle

        if self._started:
            return self

        # 配置覆写走内存层（immediate=False 不落盘），命令前缀等经热更新生效
        merged = {"ErisPulse.event.command.prefix": self.prefix, **self._config}
        for key, value in merged.items():
            config.setConfig(key, value)

        # 关闭事件去重：合成事件的 id 若重复会被框架静默吞掉
        self._dedupe_prev = getattr(adapter, "_event_dedupe_enabled", None)
        adapter._event_dedupe_enabled = False
        adapter._seen_event_ids.clear()

        # 每个 TestBot 动态生成 MockAdapter 子类再注册：框架对"同类实例"会
        # 复用绑定，动态子类保证多个 TestBot（同一进程多用例）各自持有独立的
        # 出站记录，互不串台
        adapter_cls = type(
            f"MockAdapter_{self.platform}_{id(self):x}", (MockAdapter,), {}
        )
        adapter.register(self.platform, adapter_cls)
        self._adapter = adapter.get(self.platform)

        for event_name in _OBSERVED_LIFECYCLE_EVENTS:
            hook = self._make_collector(event_name)
            lifecycle.register(event_name, hook)
            self._lifecycle_hooks.append((event_name, hook))

        self._started = True
        return self

    async def shutdown(self) -> None:
        """
        停止并清理：卸载已加载模块、清理命令 / 消息 / 适配器全局状态、
        移除生命周期采集器、恢复事件去重设置
        """
        from ErisPulse import lifecycle

        for name in list(self._loaded_modules):
            try:
                await self.unload_module(name)
            except Exception:
                pass

        # 清理命令 / 消息 / 适配器全局单例状态（清单与框架官方测试套件一致）
        from ErisPulse.Core.adapter import adapter as _adapter_mgr
        from ErisPulse.Core.Event import _clear_all_handlers
        from ErisPulse.Core.Event.command import command as _command_handler
        from ErisPulse.Core.Event.interaction import interaction
        from ErisPulse.Core.Event.message import message as _message_handler

        _clear_all_handlers()
        _command_handler.commands.clear()
        _command_handler.aliases.clear()
        _command_handler.groups.clear()
        _command_handler.permissions.clear()
        _command_handler._cooldowns.clear()
        _command_handler._max_name_tokens = 1
        _message_handler.handler.handlers.clear()
        _message_handler.handler._handler_map.clear()
        _adapter_mgr._onebot_handlers.clear()
        _adapter_mgr._raw_handlers.clear()
        _adapter_mgr._onebot_middlewares.clear()
        _adapter_mgr._bots.clear()
        _adapter_mgr._adapters.pop(self.platform, None)
        _adapter_mgr._adapter_info.pop(self.platform, None)

        interaction.clear()

        # 重挂命令分发器：_clear_commands 会把分发器从共享 handler 注销
        # （标志位复位），后续用例若未先注册任何命令，wait_reply 的
        # 交互解析（_check_pending_reply）与命令分发都将无人接管
        _command_handler._register_dispatcher()
        if self._dedupe_prev is None:
            _adapter_mgr._event_dedupe_enabled = None
        else:
            _adapter_mgr._event_dedupe_enabled = self._dedupe_prev

        for event_name, hook in self._lifecycle_hooks:
            lifecycle.unregister(event_name, hook)
        self._lifecycle_hooks.clear()
        self._observed = {name: [] for name in _OBSERVED_LIFECYCLE_EVENTS}
        self._loaded_modules.clear()
        self._started = False

    async def __aenter__(self) -> TestBot:
        return await self.startup()

    async def __aexit__(self, *exc_info) -> None:
        await self.shutdown()

    def _make_collector(self, event_name: str):
        """
        构造生命周期事件采集器

        :param event_name: 事件名
        :return: 异步钩子函数，把事件 data 追加到 self._observed
        """

        async def _collect(data: dict | None = None, *_args, **_kwargs):
            self._observed.setdefault(event_name, []).append(data or {})

        _collect._erispulse_testing_collector = event_name
        return _collect

    # ==================== 事件分发 ====================

    async def dispatch(self, event: dict[str, Any], *, drain: bool = True) -> DispatchTrace:
        """
        分发一条事件，默认等待全部处理器落地，并返回分发决策链

        框架的处理器是 fire-and-forget Task；本方法 emit 后 gather 在途
        Task，调用返回即处理完成——断言无需 sleep。决策链记录本次分发
        经过的每个判定点（命令命中 / 作用域 / 权限 / 冷却 / 执行结果 /
        中间件否决），直接回答"命令为什么没触发"。

        :param event: 事件 dict（由 create_*_event 工厂构造）
        :param drain: 是否等待处理器落地（默认 True）。``wait_reply`` 等
            交互式处理器会长驻挂起，触发交互的首次消息应传 ``drain=False``；
            后续 ``reply_as`` 会统一等待全部任务（含被唤醒的处理器）收口
        :return: DispatchTrace——``trace.verdict`` / ``trace.explain()`` /
            ``trace.assert_executed()`` 等
        """
        from ErisPulse import adapter
        from ErisPulse.Core.Event.trace import start_dispatch_trace

        with start_dispatch_trace() as records:
            await adapter.emit(event)
            if drain:
                await self._drain_handlers()
        trace = DispatchTrace(records)
        self._traces.append(trace)
        return trace

    async def send_message(self, text: str, **event_kwargs: Any) -> None:
        """
        以默认用户身份分发一条消息（create_message_event 的快捷方式）

        :param text: 消息文本
        :param event_kwargs: 透传给 create_message_event 的参数（user_id / group_id ...）
        """
        event_kwargs.setdefault("platform", self.platform)
        event_kwargs.setdefault("bot_id", self.bot_id)
        event_kwargs.setdefault("user_id", self.user_id)
        await self.dispatch(create_message_event(text, **event_kwargs))

    async def _drain_handlers(self, timeout: float = 5.0) -> None:
        """
        等待在途事件处理器 Task 全部退出

        :param timeout: 最长等待秒数
        """
        from ErisPulse import adapter

        pending = list(getattr(adapter, "_pending_handler_tasks", ()))
        if pending:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=timeout,
            )
        # lifecycle.fire 的后台钩子不在 _pending_handler_tasks 内，
        # 多让渡几拍让其在同轮调度内落地（否决审计 / 发送回执等观测点）
        for _ in range(3):
            await asyncio.sleep(0)

    # ==================== 模块管理 ====================

    async def load_module(self, target: str | type) -> str:
        """
        加载被测模块

        :param target: 模块注册名（entry-point 已注册的包）或 BaseModule 子类
        :return: 模块注册名
        """
        from ErisPulse import module

        if isinstance(target, str):
            name = target
        else:
            meta = getattr(target, "get_meta", None)
            name = None
            if meta is not None:
                try:
                    name = meta().name
                except Exception:
                    name = None
            name = name or target.__name__
            module.register(name, target)
        await module.load(name)
        self._loaded_modules.append(name)
        return name

    async def unload_module(self, name: str) -> None:
        """
        卸载已加载的模块

        :param name: 模块注册名
        """
        from ErisPulse import module

        await module.unload(name)
        if name in self._loaded_modules:
            self._loaded_modules.remove(name)

    # ==================== 出站断言 ====================

    @property
    def replies(self) -> list[SentMessage]:
        """全部出站消息（按发送顺序）"""
        return list(self._adapter.sent) if self._adapter else []

    @property
    def last_reply(self) -> SentMessage | None:
        """最近一次出站消息（无出站时为 None）——RFC 断言形态 bot.last_reply.text"""
        return self._adapter.last_sent if self._adapter else None

    def replies_to(self, target_id: str | int) -> list[SentMessage]:
        """
        过滤发往指定目标的消息

        :param target_id: 目标 ID（user_id / group_id）
        :return: 匹配的 SentMessage 列表
        """
        return [r for r in self.replies if str(r.target_id) == str(target_id)]

    def clear_replies(self) -> None:
        """清空出站记录（阶段间隔离断言）"""
        if self._adapter:
            self._adapter.clear()

    def assert_replied(self, contains: str | None = None, *, to: str | int | None = None) -> SentMessage:
        """
        断言存在出站消息（可选：包含指定文本 / 发往指定目标）

        :param contains: 期望包含的子串（None 时仅断言存在）
        :param to: 期望的目标 ID（None 时不限）
        :return: 命中的第一条 SentMessage
        :raises AssertionError: 无匹配出站时
        """
        pool = self.replies_to(to) if to is not None else self.replies
        if contains is None:
            assert pool, "expected at least one outbound message, got none"
            return pool[0]
        for reply in pool:
            if reply.contains(contains):
                return reply
        raise AssertionError(
            f"no outbound message contains {contains!r}; got: {[r.text for r in pool]!r}"
        )

    def assert_not_replied(self) -> None:
        """
        断言没有任何出站消息

        :raises AssertionError: 存在出站时
        """
        assert not self.replies, f"expected no outbound messages, got {[r.text for r in self.replies]!r}"

    def assert_reply_contains(self, needle: str, *, to: str | int | None = None) -> None:
        """
        断言存在包含指定文本的出站消息（assert_replied(contains=...) 的别名）

        :param needle: 期望包含的子串
        :param to: 期望的目标 ID（可选）
        """
        self.assert_replied(needle, to=to)

    async def wait_for_reply(self, timeout: float = 2.0) -> SentMessage:
        """
        轮询等待出站消息出现（异步回复场景）

        :param timeout: 最长等待秒数
        :return: 最新一条 SentMessage
        :raises TimeoutError: 超时仍无出站
        """
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            await self._drain_handlers(timeout=timeout)
            if self.replies:
                return self.replies[-1]
            await asyncio.sleep(0.05)
        raise TimeoutError(f"no outbound message within {timeout}s")

    # ==================== 决策链 ====================

    @property
    def traces(self) -> list[DispatchTrace]:
        """本 TestBot 的全部分发决策链（按分发顺序）"""
        return list(self._traces)

    @property
    def last_trace(self) -> DispatchTrace | None:
        """最近一次分发的决策链（未分发过时为 None）"""
        return self._traces[-1] if self._traces else None

    # ==================== 生命周期断言 ====================

    def events(self, event_name: str) -> list[dict[str, Any]]:
        """
        获取已采集的生命周期事件数据

        :param event_name: 事件名（command.matched / command.executed /
            adapter.event.blocked / message.sending / message.sent）
        :return: 事件 data 列表（按触发顺序）
        """
        return list(self._observed.get(event_name, []))

    @property
    def last_command(self) -> dict[str, Any] | None:
        """最近一次命令匹配信息（event["command"]，无命中时为 None）"""
        matched = self.events("command.matched")
        return matched[-1] if matched else None

    def assert_command_executed(self, name: str) -> dict[str, Any]:
        """
        断言指定命令已成功执行

        :param name: 命令名
        :return: 对应的 command.executed 事件 data
        :raises AssertionError: 未找到成功执行记录时
        """
        for data in self.events("command.executed"):
            if data.get("command") == name and data.get("success"):
                return data
        raise AssertionError(
            f"command {name!r} was not executed successfully; "
            f"executed events: {self.events('command.executed')!r}"
        )

    @property
    def blocked_events(self) -> list[dict[str, Any]]:
        """被中间件否决的事件（adapter.event.blocked 审计数据）"""
        return self.events("adapter.event.blocked")

    # ==================== 依赖替换与交互 ====================

    @contextmanager
    def patch_dependency(self, dependency: Any, value: Any = None):
        """
        临时替换一个依赖函数（Depends 声明引用的函数）

        命令注册表中持有 ``Depends(dependency)`` 声明；本方法把其中指向
        ``dependency`` 的声明换装为 Mock（``use_cache`` 等其余属性不变），
        框架解析依赖时即拿到 Mock。with 退出自动还原原函数。

        :param dependency: 被 Depends(...) 引用的依赖函数
        :param value: 替换后依赖的返回值
        :yields: Mock 对象（可断言 call_args 等）
        """
        import inspect

        from ErisPulse.Core.Event.command import command as _cmd

        is_async = inspect.iscoroutinefunction(dependency)
        mock: Any = AsyncMock(return_value=value) if is_async else Mock(return_value=value)
        swapped: list[Any] = []
        for info in _cmd.commands.values():
            for dep in (info.get("depends") or {}).values():
                if dep.dependency is dependency:
                    object.__setattr__(dep, "dependency", mock)
                    swapped.append(dep)
        try:
            yield mock
        finally:
            for dep in swapped:
                object.__setattr__(dep, "dependency", dependency)

    async def reply_as(
        self,
        text: str,
        *,
        user_id: str | None = None,
        group_id: str | None = None,
        settle: float = 0.05,
        registration_wait: float = 2.0,
    ) -> None:
        """
        以指定用户身份发送一条后续消息（模拟 wait_reply 的用户回复）

        发送前先等待交互 waiter 就绪：触发交互的首次消息（``drain=False``
        分发）的处理器完成 ``wait_reply`` 注册需要若干调度轮次（可能包含
        存储桥接等首次初始化），过早回复会错过交互命中。以轮询会话键上
        的等待条目取代盲等，就绪后立即发送。

        :param text: 消息文本
        :param user_id: 用户 ID（缺省 TestBot 默认用户）
        :param group_id: 群 ID（缺省私聊）
        :param settle: 基础调度让渡时长（秒）
        :param registration_wait: 等待 waiter 注册的最长时间（秒），超时照常发送
        """
        if settle > 0:
            await asyncio.sleep(settle)
        key = self._interaction_key(user_id or self.user_id, group_id)
        if key is not None:
            from ErisPulse.Core.Event.interaction import interaction

            loop = asyncio.get_running_loop()
            deadline = loop.time() + registration_wait
            while loop.time() < deadline and not interaction._find_entry(key):
                await asyncio.sleep(0.02)
        await self.send_message(text, user_id=user_id or self.user_id, group_id=group_id)

    def _interaction_key(self, user_id: str, group_id: str | None) -> str | None:
        """
        构造交互会话键（platform:bot:user:target，与 interaction.make_key 同构）

        :param user_id: 用户 ID
        :param group_id: 群 ID（None 表示私聊，target 取 user_id）
        :return: 会话键字符串
        """
        if not self._started:
            return None
        return f"{self.platform}:{self.bot_id}:{user_id}:{group_id or user_id}"

    @property
    def adapter(self) -> MockAdapter:
        """
        获取 MockAdapter 实例（自定义断言入口）

        :return: 已注册的 MockAdapter
        :raises RuntimeError: startup 尚未调用时
        """
        if self._adapter is None:
            raise RuntimeError("TestBot is not started; use 'async with bot:' or await bot.startup()")
        return self._adapter

    def __repr__(self) -> str:
        return f"TestBot(platform={self.platform!r}, bot_id={self.bot_id!r}, started={self._started})"


def _iter_replies_text(replies: Iterable[SentMessage]) -> list[str]:
    """取一组出站消息的文本列表（错误信息展示用）"""
    return [r.text for r in replies]
