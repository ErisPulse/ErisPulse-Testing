"""
ErisPulse-Testing 自测

覆盖 RFC 承诺 API 与断言面：命令分发与注入、回复记录断言、
模块加载/卸载、wait_reply 模拟、依赖替换、生命周期采集、
事件工厂、自定义前缀配置、分发决策链、被测适配器（DUT）。
"""

import pytest
from ErisPulse.Core.Event.command import command as command_registry

from ErisPulse_Testing import (
    TestBot,
    create_command_event,
    create_message_event,
    create_meta_event,
    create_notice_event,
    create_request_event,
)

# ==================== 事件工厂 ====================


class TestEventFactories:
    def test_message_event_shape(self):
        event = create_message_event("hello", user_id="u1", group_id="g1")
        assert event["type"] == "message"
        assert event["detail_type"] == "group"
        assert event["user_id"] == "u1"
        assert event["group_id"] == "g1"
        assert event["message"][0]["data"]["text"] == "hello"
        assert event["alt_message"] == "hello"
        assert event["id"] != create_message_event("hello")["id"]  # uuid 唯一

    def test_command_event_adds_prefix(self):
        event = create_command_event("roll 3")
        assert event["alt_message"] == "/roll 3"
        # 已带前缀不重复
        assert create_command_event("/roll")["alt_message"] == "/roll"

    def test_notice_request_meta(self):
        notice = create_notice_event("friend_add", user_id="u2")
        assert notice["type"] == "notice" and notice["detail_type"] == "friend_add"
        request = create_request_event("friend", comment="hi")
        assert request["comment"] == "hi"
        meta = create_meta_event("connect")
        assert meta["type"] == "meta"


# ==================== 命令分发与回复断言 ====================


class TestCommandDispatch:
    async def test_command_replies_and_asserts(self, bot: TestBot):
        @command_registry("hello", help="打招呼")
        async def hello(event):
            await event.reply("你好，世界")

        await bot.dispatch(create_command_event("hello", user_id="123"))

        bot.assert_replied()
        assert bot.last_reply.text == "你好，世界"
        bot.assert_reply_contains("世界")
        bot.assert_command_executed("hello")
        assert bot.last_command["command"] == "hello"

    async def test_args_injection(self, bot: TestBot):
        @command_registry("roll", args="<count:int> [sides:int=6]")
        async def roll(event, count: int, sides: int = 6):
            await event.reply(f"{count}d{sides}")

        await bot.dispatch(create_command_event("roll 3 20", user_id="u9"))
        assert bot.last_reply.text == "3d20"

    async def test_assert_not_replied(self, bot: TestBot):
        await bot.send_message("普通消息，不是命令")
        bot.assert_not_replied()

    async def test_replies_to_filter(self, bot: TestBot):
        @command_registry("who")
        async def who(event):
            await event.reply(f"hi {event.get_user_id()}")

        await bot.dispatch(create_command_event("who", user_id="a"))
        await bot.dispatch(create_command_event("who", user_id="b"))
        assert [r.text for r in bot.replies_to("a")] == ["hi a"]

    async def test_wait_for_reply(self, bot: TestBot):
        @command_registry("later")
        async def later(event):
            import asyncio

            await asyncio.sleep(0.2)
            await event.reply("delayed")

        import asyncio

        task = asyncio.create_task(bot.dispatch(create_command_event("later")))
        # dispatch 内部会等 handler 落地；直接等它完成再断言（wait_for_reply 演示独立等待）
        await task
        assert bot.last_reply.text == "delayed"

    async def test_clear_replies(self, bot: TestBot):
        @command_registry("ping")
        async def ping(event):
            await event.reply("pong")

        await bot.dispatch(create_command_event("ping"))
        assert bot.replies
        bot.clear_replies()
        bot.assert_not_replied()


# ==================== 模块加载 / 卸载 ====================


class TestModuleLifecycle:
    async def test_load_module_by_class(self, bot: TestBot):
        from ErisPulse.Core.Bases.module import BaseModule

        class DemoModule(BaseModule):
            async def on_load(self, event=None) -> bool:
                @command_registry("demo_cmd")
                async def demo_cmd(event):
                    await event.reply("demo ok")

                return True

            async def on_unload(self, event=None) -> bool:
                return True

            @staticmethod
            def get_meta():
                from ErisPulse.Core.Bases.module import ModuleMeta

                return ModuleMeta(name="DemoModule", version="0.1.0")

        name = await bot.load_module(DemoModule)
        assert name == "DemoModule"

        await bot.dispatch(create_command_event("demo_cmd"))
        assert bot.last_reply.text == "demo ok"

        await bot.unload_module("DemoModule")
        bot.clear_replies()
        await bot.dispatch(create_command_event("demo_cmd"))
        bot.assert_not_replied()  # 卸载后命令失效


# ==================== wait_reply 模拟 ====================


class TestInteraction:
    async def test_reply_as_wakes_wait_reply(self, bot: TestBot):
        from ErisPulse.Core.Event.message import message as message_handler

        answers = []

        @message_handler.on_message()
        async def asker(event):
            answer = await event.wait_reply("请输入年龄：", timeout=3)
            if answer:
                answers.append(answer.get_alt_message())

        # 触发交互的首次消息不等待（wait_reply 处理器长驻挂起）
        await bot.dispatch(create_message_event("开始"), drain=False)
        await bot.reply_as("18")  # 回复统一收口：含被唤醒的处理器
        assert answers == ["18"]


# ==================== 依赖替换 ====================


class TestDependencyOverride:
    async def test_patch_dependency(self, bot: TestBot):
        from ErisPulse.Core.di import Depends

        async def get_balance(user_id):
            return 100

        @command_registry("balance")
        async def balance(event, amount=Depends(get_balance)):
            await event.reply(f"余额 {amount}")

        with bot.patch_dependency(get_balance, 999) as mock_dep:
            await bot.dispatch(create_command_event("balance", user_id="u5"))
            assert bot.last_reply.text == "余额 999"
            assert mock_dep.called


# ==================== 生命周期采集 ====================


class TestLifecycleObservation:
    async def test_executed_failure_observed(self, bot: TestBot):
        @command_registry("boom")
        async def boom(event):
            raise ValueError("炸了")

        await bot.dispatch(create_command_event("boom"))
        executed = bot.events("command.executed")
        assert executed and executed[-1]["success"] is False


# ==================== 自定义配置 ====================


class TestCustomConfig:
    async def test_custom_prefix(self, quiet_bot: TestBot):
        @command_registry("cfgcmd")
        async def cfgcmd(event):
            await event.reply("prefix works")

        from ErisPulse_Testing import create_message_event as cme

        await quiet_bot.dispatch(cme("//cfgcmd"))
        assert quiet_bot.last_reply.text == "prefix works"


# ==================== 中间件否决审计 ====================


class TestBlockedObservation:
    async def test_middleware_veto_blocked_event(self, bot: TestBot):
        from ErisPulse.Core import adapter as adapter_mgr

        @adapter_mgr.middleware
        async def firewall(data):
            if data.get("alt_message") == "/secret":
                return False
            return None

        try:
            @command_registry("secret")
            async def secret(event):
                await event.reply("should not")

            await bot.dispatch(create_command_event("secret"))
            assert bot.assert_not_replied() is None
            assert bot.blocked_events, "expected adapter.event.blocked observation"
        finally:
            adapter_mgr._onebot_middlewares.clear()


# ==================== pytest 插件 fixtures ====================


class TestPluginFixtures:
    async def test_default_testbot_fixture(self, testbot):
        assert testbot._started
        assert testbot.platform == "test"

    async def test_make_testbot_factory(self, make_testbot):
        async with make_testbot(prefix="//", bot_id="bot_y") as bot:
            assert bot.prefix == "//"

            @command_registry("fx")
            async def fx(event):
                await event.reply("ok")

            from ErisPulse_Testing import create_command_event as cce

            await bot.dispatch(cce("fx", prefix="//"))
            assert bot.last_reply.text == "ok"


# ==================== 分发决策链（方向五）====================


class TestDispatchTrace:
    async def test_executed_trace(self, bot):
        @command_registry("tr_ok")
        async def tr_ok(event):
            await event.reply("done")

        trace = await bot.dispatch(create_command_event("tr_ok"))
        trace.assert_executed("tr_ok")
        assert trace.executed and trace.command == "tr_ok"
        assert "✓" in trace.explain()
        assert bot.last_trace is trace

    async def test_no_match_trace_with_suggestion(self, bot):
        @command_registry("tr_real")
        async def tr_real(event):
            await event.reply("x")

        trace = await bot.dispatch(create_command_event("tr_reall"))
        trace.assert_no_match()
        step = trace.steps("command_match")[0]
        assert step["params"]["suggestion"] == "tr_real"

    async def test_cooldown_dropped_trace(self, bot):
        @command_registry("tr_cd", cooldown="1h")
        async def tr_cd(event):
            await event.reply("ok")

        await bot.dispatch(create_command_event("tr_cd"))
        trace = await bot.dispatch(create_command_event("tr_cd"))
        trace.assert_dropped()
        assert "cooldown" in trace.explain()

    async def test_passed_through_trace(self, bot):
        trace = await bot.dispatch(create_message_event("普通聊天"))
        assert trace.verdict == "passed"
        assert trace.steps("dispatch")

    async def test_middleware_veto_trace(self, bot):
        from ErisPulse.Core import adapter as adapter_mgr

        @adapter_mgr.middleware
        async def veto_all(data):
            return False

        try:
            trace = await bot.dispatch(create_message_event("/whatever"))
            assert trace.verdict == "dropped"
            assert trace.steps("middleware")
        finally:
            adapter_mgr._onebot_middlewares.clear()


# ==================== 被测适配器（DUT）====================


class TestAdapterUnderTest:
    """适配器测试支持：load_adapter / start_adapter / feed_raw / call_api 间谍"""

    def _make_adapter_class(self):
        from ErisPulse import BaseAdapter

        class MiniAdapter(BaseAdapter):
            class Send(BaseAdapter.Send):
                def Raw_ob12(self, message, **kwargs):
                    """出站消息段 → call_api（经 TestBot 的间谍记录）"""
                    import asyncio

                    adapter_instance = self._adapter

                    async def _send():
                        segments = self._apply_modifiers(message)
                        return await adapter_instance.call_api(
                            "send_message", message=segments, **self.send_context
                        )

                    return asyncio.create_task(_send())

            async def start(self):
                pass

            async def shutdown(self):
                pass

            async def call_api(self, endpoint, **params):
                raise RuntimeError("real network call should be spied")

            def convert(self, raw):
                from ErisPulse_Testing import create_message_event

                return create_message_event(
                    raw.get("text", ""),
                    platform=self._platform,
                    bot_id="bot_x",
                )

        return MiniAdapter

    async def test_load_adapter_registers_and_spies_call_api(self, bot):
        Mini = self._make_adapter_class()
        plat = bot.load_adapter(Mini, platform="dut", config={"token": "t"})
        assert plat == "dut"
        assert bot.dut is not None

        # call_api 被间谍替换：不触网、记录调用、返回标准响应
        resp = await bot.dut.call_api("get_login_info", user_id="u1")
        assert resp["status"] == "ok"
        assert bot.dut_api_calls == [{"endpoint": "get_login_info", "user_id": "u1"}]

    async def test_dut_replaces_mock_on_same_platform(self, bot):
        """平台名与 TestBot 相同时替换记录型适配器——出站断言改走 dut_api_calls"""
        Mini = self._make_adapter_class()
        bot.load_adapter(Mini)  # 平台 = test（与 TestBot 相同）

        @command_registry("hello")
        async def hello(event):
            await event.reply("hi")

        await bot.dispatch(
            __import__("ErisPulse_Testing", fromlist=["create_message_event"])
            .create_message_event("/hello")
        )
        assert bot.dut_api_calls  # 出站经被测适配器产生 API 调用记录

    async def test_start_stop_adapter(self, bot):
        Mini = self._make_adapter_class()
        started, stopped = [], []

        class StartyMini(Mini):
            async def start(self):
                started.append(1)

            async def shutdown(self):
                stopped.append(1)

        bot.load_adapter(StartyMini, platform="dut2")
        await bot.start_adapter()
        assert started == [1]
        await bot.stop_adapter()
        assert stopped == [1]

    async def test_feed_raw_via_convert(self, bot):
        """feed_raw → convert → 命令分发 → 回复经 DUT 的 Send DSL 发出并被间谍记录"""
        import json

        Mini = self._make_adapter_class()
        bot.load_adapter(Mini, platform="dut3")

        @command_registry("dutping")
        async def dutping(event):
            await event.reply("pong")

        await bot.feed_raw({"text": "/dutping"})
        blob = json.dumps(bot.dut_api_calls, ensure_ascii=False)
        assert "pong" in blob

    async def test_feed_raw_without_convert_raises(self, bot):
        from ErisPulse import BaseAdapter

        class NoConvert(BaseAdapter):
            async def start(self):
                pass

            async def shutdown(self):
                pass

            async def call_api(self, endpoint, **params):
                return {}

        bot.load_adapter(NoConvert, platform="dut4")
        with pytest.raises(AttributeError):
            await bot.feed_raw({"text": "x"})
