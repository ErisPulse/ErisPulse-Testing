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

from ._compat import HAS_DISPATCH_TRACE, require_ep29


def _final_verdict_fallback(records: list[dict[str, Any]]) -> str:
    """final_verdict 的本地兜底（SDK 无 ErisPulse.Core.Event.trace 时使用，逻辑同源）"""
    if not records:
        return "unknown"
    verdicts = [r.get("verdict") for r in records]
    if "failed" in verdicts:
        return "failed"
    if "executed" in verdicts:
        return "executed"
    if "rejected" in verdicts:
        return "rejected"
    if "dropped" in verdicts:
        return "dropped"
    if any(r.get("stage") == "command_match" and r.get("verdict") == "missed" for r in records):
        return "no_match"
    if any(r.get("stage") == "dispatch" and r.get("verdict") == "passed" for r in records):
        return "passed"
    return "unknown"


def _format_dispatch_trace_fallback(records: list[dict[str, Any]]) -> str:
    """format_dispatch_trace 的本地兜底（stage -> verdict 简易渲染，无 i18n）"""
    if not records:
        return "（决策链不可用：需要 ErisPulse>=2.9.0-dev）"
    lines: list[str] = []
    for record in records:
        verdict = record.get("verdict")
        marker = "✓" if verdict == "ok" else ("✗" if verdict in ("rejected", "failed", "dropped") else "·")
        lines.append(f"{marker} {record.get('stage')} -> {verdict}")
    return "\n".join(lines)


class DispatchTrace:
    """一次事件分发的决策链记录与断言面"""

    def __init__(self, records: list[dict[str, Any]]):
        self.records: list[dict[str, Any]] = list(records)

    @property
    def available(self) -> bool:
        """
        决策链数据源是否可用（ErisPulse>=2.9.0-dev）

        False 时（如 EP 2.8.x）dispatch 照常工作、replies 断言照常可用，
        但 records 恒为空、verdict 恒为 "unknown"。
        """
        return HAS_DISPATCH_TRACE

    @property
    def verdict(self) -> str:
        """最终结论（executed / rejected / dropped / failed / no_match / passed / unknown）"""
        try:
            from ErisPulse.Core.Event.trace import final_verdict
        except ImportError:
            final_verdict = _final_verdict_fallback

        return final_verdict(self.records)

    def explain(self) -> str:
        """渲染为人类可读的因果链文本（当前语言）"""
        try:
            from ErisPulse.Core.Event.trace import format_dispatch_trace
        except ImportError:
            format_dispatch_trace = _format_dispatch_trace_fallback

        return format_dispatch_trace(self.records)

    def _require_available(self, api: str) -> None:
        """断言族门禁：无决策链数据源时给出明确版本错误，避免误导性失败"""
        if not HAS_DISPATCH_TRACE:
            require_ep29(f"DispatchTrace.{api}（分发决策链断言）")

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
        :raises RuntimeError: 决策链数据源不可用（需 ErisPulse>=2.9.0-dev）
        """
        self._require_available("assert_executed")
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
        self._require_available("assert_rejected")
        if self.verdict != "rejected":
            raise AssertionError(f"expected rejected, got {self.verdict!r}:\n{self.explain()}")
        return self

    def assert_dropped(self) -> DispatchTrace:
        """
        断言命令被静默丢弃（如冷却命中）

        :return: self
        :raises AssertionError: 结论不符时
        """
        self._require_available("assert_dropped")
        if self.verdict != "dropped":
            raise AssertionError(f"expected dropped, got {self.verdict!r}:\n{self.explain()}")
        return self

    def assert_no_match(self) -> DispatchTrace:
        """
        断言未命中任何注册命令

        :return: self
        :raises AssertionError: 结论不符时
        """
        self._require_available("assert_no_match")
        if self.verdict != "no_match":
            raise AssertionError(f"expected no_match, got {self.verdict!r}:\n{self.explain()}")
        return self

    def __repr__(self) -> str:
        return f"DispatchTrace(verdict={self.verdict!r}, steps={len(self.records)})"
