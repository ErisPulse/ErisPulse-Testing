"""
pytest 集成：提供 testbot fixture

经 [project.entry-points.pytest11] 注册，安装 ErisPulse-Testing 后自动可用。
fixture 为 function 级（每个用例独立环境），需配合 pytest-asyncio 的
asyncio_mode=auto 或 @pytest.mark.asyncio 使用。

{!--< tips >!--}
1. ``async def test_x(testbot):`` 直接使用，用例结束自动清理
2. 需要 TestBot 参数时用 ``@pytest.fixture`` 包装 ``make_testbot`` 工厂
{!--< /tips >!--}
"""

from __future__ import annotations

import pytest

from .bot import TestBot


@pytest.fixture
async def testbot():
    """function 级 TestBot：默认平台 / 前缀，用例结束自动 shutdown 清理"""
    bot = TestBot()
    async with bot:
        yield bot


@pytest.fixture
def make_testbot():
    """
    TestBot 工厂 fixture：需要自定义参数（platform / prefix / config）时使用

    :example:
    >>> def test_custom_prefix(make_testbot):
    ...     async with make_testbot(prefix="//") as bot:
    ...         ...
    """
    created: list[TestBot] = []

    def _factory(**kwargs) -> TestBot:
        bot = TestBot(**kwargs)
        created.append(bot)
        return bot

    yield _factory

    # 非 async with 用法兜底清理（同步上下文尽力而为）
    import asyncio

    for bot in created:
        if bot._started:
            try:
                asyncio.get_event_loop().run_until_complete(bot.shutdown())
            except Exception:
                pass
