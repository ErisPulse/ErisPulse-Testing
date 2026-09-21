"""
SentMessage —— 出站消息记录

MockAdapter 捕获到的每一次发送都记录为 SentMessage，供 TestBot 断言使用。

{!--< tips >!--}
1. text 为首个 text 段的内容（纯文本快捷访问），完整分段见 segments
2. target_type / target_id / bot_id 来自发送上下文（Send.To / Using 链）
3. modifiers 记录 At / AtAll / Reply 修饰器状态
{!--< /tips >!--}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass(frozen=True)
class SentMessage:
    """
    MockAdapter 记录的一条出站消息

    :ivar text: 首个 text 段的文本内容（无 text 段时为空字符串）
    :ivar segments: 合并修饰器后的完整 OneBot12 消息段列表
    :ivar target_type: 发送目标类型（user / group / channel ...）
    :ivar target_id: 发送目标 ID
    :ivar bot_id: 发送账号（Send.Using 指定，可能为空）
    :ivar platform: 适配器平台名
    :ivar timestamp: 记录时刻（time.time() 秒）
    """

    text: str
    segments: tuple[dict[str, Any], ...]
    target_type: str | None
    target_id: str | int | None
    bot_id: str | int | None
    platform: str
    timestamp: float = field(default_factory=time)

    @classmethod
    def build(
        cls,
        segments: list[dict[str, Any]],
        context: dict[str, Any],
        platform: str,
    ) -> SentMessage:
        """
        从消息段与发送上下文构造记录

        :param segments: 合并修饰器后的消息段列表
        :param context: send_context（target_type / target_id / account_id）
        :param platform: 适配器平台名
        :return: SentMessage 实例
        """
        text = ""
        for seg in segments:
            if isinstance(seg, dict) and seg.get("type") == "text":
                text = str((seg.get("data") or {}).get("text", ""))
                break
        return cls(
            text=text,
            segments=tuple(segments),
            target_type=context.get("target_type"),
            target_id=context.get("target_id"),
            bot_id=context.get("account_id"),
            platform=platform,
        )

    def contains(self, needle: str) -> bool:
        """
        判断文本内容是否包含指定子串

        :param needle: 待查找的子串
        :return: 包含返回 True
        """
        return needle in self.text

    def has_modifier(self, seg_type: str) -> bool:
        """
        判断消息是否携带指定类型的修饰段（at / reply / mention_all ...）

        :param seg_type: 消息段类型名
        :return: 携带返回 True
        """
        return any(isinstance(seg, dict) and seg.get("type") == seg_type for seg in self.segments)
