"""
版本特性探测层

ErisPulse-Testing 的核心功能（TestBot 生命周期、事件工厂、dispatch 免 sleep
drain、出站捕获与断言、wait_reply 模拟、模块加载）兼容 ErisPulse 2.8.5+；
以下高级能力依赖 2.9.0-dev 引入的 SDK 特性，运行时按探测结果降级：

- 分发决策链（DispatchTrace 因果链）→ ``ErisPulse.Core.Event.trace``
- 依赖替换（patch_dependency）→ ``ErisPulse.Core.di``（Depends 体系）
- 命令装饰器 ``args=`` / ``cooldown=`` 等治理参数 → 2.9 命令治理
- 中间件否决观测（adapter.event.blocked）→ 2.9 的 False 否决契约

探测用 find_spec / hasattr / 签名检查而非版本号解析：对 dev 版本后缀
天然免疫，也不依赖 runtime/version（2.8.5 才引入，不够通用）。

{!--< tips >!--}
1. 核心功能无版本门槛；高级特性缺失时经 require_ep29 抛出明确错误
2. 测试用例可用这些标志做 skipif 门禁（tests/test_testbot.py 同款）
{!--< /tips >!--}
"""

from __future__ import annotations

import importlib.util
import inspect
from functools import lru_cache

EP29_REQUIRED = "2.9.0-dev"


def _has_module(name: str) -> bool:
    """模块是否存在（find_spec 探测，不实际执行模块代码）"""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


HAS_DISPATCH_TRACE = _has_module("ErisPulse.Core.Event.trace")
HAS_DI = _has_module("ErisPulse.Core.di")


@lru_cache(maxsize=None)
def has_command_decorator_kwarg(name: str) -> bool:
    """
    命令注册装饰器是否支持指定参数（``args`` / ``cooldown`` 等，2.9.0-dev 起）

    :param name: 参数名
    :return: 装饰器签名中包含该参数时 True
    """
    try:
        from ErisPulse.Core.Event.command import command

        params = inspect.signature(command.__call__).parameters
    except Exception:
        return False
    return name in params


@lru_cache(maxsize=None)
def has_event_veto() -> bool:
    """中间件 False 否决契约（adapter.event.blocked，2.9.0-dev 起）是否存在"""
    try:
        from ErisPulse.Core import constants
    except Exception:
        return False
    return hasattr(constants, "EVENT_ADAPTER_EVENT_BLOCKED")


def sdk_version() -> str:
    """当前安装的 ErisPulse 版本（获取失败时为 'unknown'）"""
    try:
        import ErisPulse

        return getattr(ErisPulse, "__version__", "unknown")
    except Exception:
        return "unknown"


def require_ep29(feature: str) -> None:
    """
    高级特性门禁：当前 SDK 不具备该特性时抛 RuntimeError

    :param feature: 特性名称（用于错误信息）
    :raises RuntimeError: 特性不可用时
    """
    raise RuntimeError(
        f"{feature} 需要 ErisPulse>={EP29_REQUIRED}，当前安装版本为 {sdk_version()}。"
        f"核心测试功能（dispatch / 出站断言 / wait_reply / 模块加载）在当前版本仍可使用。"
    )
