"""
DispatchTrace —— 分发决策链

TestBot.dispatch() 的返回值：把一次事件分发经过的每个判定点（命令命中、
作用域 / ACL / 主人 / 权限、冷却、参数解析、执行结果、中间件否决）串成
一条因果链，直接回答"命令为什么没触发"。

{!--< tips >!--}
1. trace.verdict: executed / rejected / dropped / failed / no_match / passed / unknown
2. trace.explain() 输出当前语言的逐行因果说明
3. 记录本身是机器可读 dict（stage / verdict / message_key / params）
{!--< /tips >!--}
"""

from __future__ import annotations

from typing import Any


class DispatchTrace:
    """一次事件分发的决策链记录与断言面"""

    def __init__(self, records: list[dict[str, Any]]):
        self.records: list[dict[str, Any]] = list(records)

    @property
    def verdict(self) -> str:
        """最终结论（executed / rejected / dropped / failed / no_match / passed / unknown）"""
        from ErisPulse.Core.Event.trace import final_verdict

        return final_verdict(self.records)

    def explain(self) -> str:
        """渲染为人类可读的因果链文本（当前语言）"""
        from ErisPulse.Core.Event.trace import format_dispatch_trace

        return format_dispatch_trace(self.records)

    def steps(self, stage: str | None = None) -> list[dict[str, Any]]:
        """
        获取判定记录（可按阶段过滤）

        :param stage: 阶段标识（command_match / scope / acl / master /
            permission / cooldown / args / execute / middleware / dispatch）；
            None 返回全部
        :return: 记录列表
        """
        if stage is None:
            return list(self.records)
        return [r for r in self.records if r.get("stage") == stage]

    @property
    def executed(self) -> bool:
        """命令是否成功执行"""
        return self.verdict == "executed"

    @property
    def command(self) -> str | None:
        """本次分发命中的命令名（未命中时为 None）"""
        for r in self.steps("command_match"):
            if r.get("verdict") == "ok":
                return (r.get("params") or {}).get("command")
        return None

    def assert_executed(self, command: str | None = None) -> DispatchTrace:
        """
        断言命令已成功执行

        :param command: 期望的命令名（None 时仅断言有命令执行成功）
        :return: self（链式断言）
        :raises AssertionError: 未执行 / 命令名不符时（附完整因果链说明）
        """
        if self.verdict != "executed":
            raise AssertionError(f"expected executed, got {self.verdict!r}:\n{self.explain()}")
        if command is not None and self.command != command:
            raise AssertionError(
                f"expected command {command!r}, got {self.command!r}:\n{self.explain()}"
            )
        return self

    def assert_rejected(self) -> DispatchTrace:
        """
        断言命令被权限类判定拒绝（作用域 / ACL / 主人 / 权限）

        :return: self
        :raises AssertionError: 结论不符时
        """
        if self.verdict != "rejected":
            raise AssertionError(f"expected rejected, got {self.verdict!r}:\n{self.explain()}")
        return self

    def assert_dropped(self) -> DispatchTrace:
        """
        断言命令被静默丢弃（如冷却命中）

        :return: self
        :raises AssertionError: 结论不符时
        """
        if self.verdict != "dropped":
            raise AssertionError(f"expected dropped, got {self.verdict!r}:\n{self.explain()}")
        return self

    def assert_no_match(self) -> DispatchTrace:
        """
        断言未命中任何注册命令

        :return: self
        :raises AssertionError: 结论不符时
        """
        if self.verdict != "no_match":
            raise AssertionError(f"expected no_match, got {self.verdict!r}:\n{self.explain()}")
        return self

    def __repr__(self) -> str:
        return f"DispatchTrace(verdict={self.verdict!r}, steps={len(self.records)})"
