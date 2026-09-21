"""
ErisPulse-Testing —— ErisPulse 官方测试工具包

TestBot、测试事件工厂、MockAdapter 出站捕获与断言面（RFC EPRFC-2026-001 方向三）。

{!--< tips >!--}
1. from ErisPulse_Testing import TestBot, create_command_event
2. pytest 集成：安装后 testbot fixture 自动可用（pytest11 entry point）
{!--< /tips >!--}
"""

from .bot import TestBot
from .events import (
    create_command_event,
    create_message_event,
    create_meta_event,
    create_notice_event,
    create_request_event,
)
from .mock_adapter import MockAdapter
from .replies import SentMessage

__all__ = [
    "MockAdapter",
    "SentMessage",
    "TestBot",
    "create_command_event",
    "create_message_event",
    "create_meta_event",
    "create_notice_event",
    "create_request_event",
]
