"""
测试事件工厂

构造与框架单测同构的 OneBot11 风格事件 dict——字段结构与 ErisPulse 官方
测试套件使用的模板一致，id 使用 uuid 保证唯一（避开框架的事件去重）。

{!--< tips >!--}
1. create_message_event 是基础；create_command_event 在其上自动加命令前缀
2. platform / bot_id 缺省取 TestBot 的默认值，也可单独覆盖
{!--< /tips >!--}
"""

from __future__ import annotations

from time import time
from typing import Any
from uuid import uuid4

DEFAULT_PLATFORM = "test"
DEFAULT_BOT_ID = "test_bot"
DEFAULT_USER_ID = "tester"


def create_message_event(
    text: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    group_id: str | None = None,
    platform: str = DEFAULT_PLATFORM,
    bot_id: str = DEFAULT_BOT_ID,
    nickname: str = "Tester",
) -> dict[str, Any]:
    """
    构造一条消息事件（OneBot11 风格 dict）

    :param text: 消息文本
    :param user_id: 发送者用户 ID
    :param group_id: 群 ID（None 表示私聊）
    :param platform: 平台名
    :param bot_id: Bot 账号 ID
    :param nickname: 发送者昵称
    :return: 事件 dict，可直接交由 TestBot.dispatch 分发
    """
    data: dict[str, Any] = {
        "id": f"evt_{uuid4().hex}",
        "time": int(time()),
        "type": "message",
        "detail_type": "group" if group_id else "private",
        "platform": platform,
        "self": {"platform": platform, "user_id": bot_id},
        "user_id": user_id,
        "user_nickname": nickname,
        "message": [{"type": "text", "data": {"text": text}}],
        "alt_message": text,
    }
    if group_id:
        data["group_id"] = group_id
    return data


def create_command_event(
    command: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    group_id: str | None = None,
    platform: str = DEFAULT_PLATFORM,
    bot_id: str = DEFAULT_BOT_ID,
    prefix: str = "/",
) -> dict[str, Any]:
    """
    构造一条命令消息事件（自动附加命令前缀）

    :param command: 命令文本（不含前缀，可带参数，如 ``"roll 3 20"``）
    :param user_id: 发送者用户 ID
    :param group_id: 群 ID（None 表示私聊）
    :param platform: 平台名
    :param bot_id: Bot 账号 ID
    :param prefix: 命令前缀（默认 ``/``）
    :return: 事件 dict
    """
    text = command if command.startswith(prefix) else f"{prefix}{command}"
    return create_message_event(
        text,
        user_id=user_id,
        group_id=group_id,
        platform=platform,
        bot_id=bot_id,
    )


def create_notice_event(
    notice_type: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    group_id: str | None = None,
    platform: str = DEFAULT_PLATFORM,
    bot_id: str = DEFAULT_BOT_ID,
    **extra: Any,
) -> dict[str, Any]:
    """
    构造一条通知事件

    :param notice_type: 通知子类型（如 ``"friend_add"`` / ``"group_increase"``）
    :param user_id: 用户 ID
    :param group_id: 群 ID（可选）
    :param platform: 平台名
    :param bot_id: Bot 账号 ID
    :param extra: 附加字段
    :return: 事件 dict
    """
    data: dict[str, Any] = {
        "id": f"evt_{uuid4().hex}",
        "time": int(time()),
        "type": "notice",
        "detail_type": notice_type,
        "platform": platform,
        "self": {"platform": platform, "user_id": bot_id},
        "user_id": user_id,
    }
    if group_id:
        data["group_id"] = group_id
    data.update(extra)
    return data


def create_request_event(
    request_type: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    platform: str = DEFAULT_PLATFORM,
    bot_id: str = DEFAULT_BOT_ID,
    comment: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """
    构造一条请求事件（好友申请 / 邀请等）

    :param request_type: 请求子类型（如 ``"friend"``）
    :param user_id: 用户 ID
    :param platform: 平台名
    :param bot_id: Bot 账号 ID
    :param comment: 验证信息
    :param extra: 附加字段
    :return: 事件 dict
    """
    data: dict[str, Any] = {
        "id": f"evt_{uuid4().hex}",
        "time": int(time()),
        "type": "request",
        "detail_type": request_type,
        "platform": platform,
        "self": {"platform": platform, "user_id": bot_id},
        "user_id": user_id,
        "comment": comment,
    }
    data.update(extra)
    return data


def create_meta_event(
    detail_type: str = "connect",
    *,
    platform: str = DEFAULT_PLATFORM,
    bot_id: str = DEFAULT_BOT_ID,
    **extra: Any,
) -> dict[str, Any]:
    """
    构造一条 meta 事件（connect / heartbeat / disconnect）

    :param detail_type: meta 子类型
    :param platform: 平台名
    :param bot_id: Bot 账号 ID
    :param extra: 附加字段
    :return: 事件 dict；connect 事件经 adapter.emit 后 Bot 自动上线
    """
    data: dict[str, Any] = {
        "id": f"evt_{uuid4().hex}",
        "time": int(time()),
        "type": "meta",
        "detail_type": detail_type,
        "platform": platform,
        "self": {"platform": platform, "user_id": bot_id},
    }
    data.update(extra)
    return data
