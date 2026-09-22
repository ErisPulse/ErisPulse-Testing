"""
包自测环境

优先使用已安装的 ErisPulse；本仓库开发场景下把同级 SDK/ErisPulse/src
插入 sys.path 兜底（免 pip install -e）。
"""

import sys
from pathlib import Path

try:
    import ErisPulse  # noqa: F401
except ImportError:
    _sdk_src = Path(__file__).resolve().parent.parent.parent / "ErisPulse" / "src"
    if _sdk_src.exists():
        sys.path.insert(0, str(_sdk_src))


import pytest

from ErisPulse_Testing import TestBot

# 显式导入插件 fixture 函数（未安装包的开发场景兜底；已安装时 entry point
# 也会注册同名 fixture，conftest 内定义优先级更高，两者不冲突）
from ErisPulse_Testing.pytest_plugin import make_testbot, testbot  # noqa: F401


@pytest.fixture(autouse=True)
def _set_asyncio_timeout():
    """给 async 用例一点余量"""
    yield


@pytest.fixture
async def bot():
    """标准 TestBot（默认 platform=test, prefix=/）"""
    async with TestBot() as b:
        yield b


@pytest.fixture
async def quiet_bot():
    """自定义前缀与配置覆写的 TestBot"""
    async with TestBot(prefix="//", config={"ErisPulse.event.command.case_sensitive": False}) as b:
        yield b
