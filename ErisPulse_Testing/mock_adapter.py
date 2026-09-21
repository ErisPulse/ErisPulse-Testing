"""
MockAdapter —— 出站消息捕获适配器

继承框架 BaseAdapter，仅实现最小面（start / shutdown / call_api）并重写
``Send.Raw_ob12``：框架全部标准发送方法（Text / Image / Voice / Video / File）
与修饰链（At / AtAll / Reply）都委托到 Raw_ob12，一处拦截即可捕获所有出站。

{!--< tips >!--}
1. 每次发送记录为 SentMessage，追加到实例的 sent 列表
2. Raw_ob12 返回标准响应 dict（status=ok / retcode=0 / 递增 message_id）
3. 由 TestBot 经 adapter.register 注册，平台名可自定义
{!--< /tips >!--}
"""

from __future__ import annotations

import asyncio
from typing import Any

from ErisPulse import BaseAdapter

from .replies import SentMessage


class MockAdapter(BaseAdapter):
    """
    测试用假适配器：记录全部出站消息，从不触网

    :ivar sent: 已发送的 SentMessage 列表（按发送顺序追加）
    """

    def __init__(self, sdk=None):
        super().__init__(sdk)
        self.sent: list[SentMessage] = []
        self._message_seq = 0

    class Send(BaseAdapter.Send):
        """出站拦截：Raw_ob12 记录消息段后返回标准成功响应"""

        def Raw_ob12(self, message, **kwargs: Any) -> Any:
            """
            记录一条出站消息并返回标准成功响应

            :param message: OneBot12 消息段数组或单个消息段
            :param kwargs: 附加参数（原样忽略）
            :return: asyncio.Task，await 后返回标准响应 dict
            """
            adapter_instance = self._adapter

            async def _record():
                segments = self._apply_modifiers(message)
                if isinstance(segments, dict):
                    segments = [segments]
                adapter_instance._message_seq += 1
                adapter_instance.sent.append(
                    SentMessage.build(
                        segments,
                        self.send_context,
                        getattr(adapter_instance, "_platform", "") or "",
                    )
                )
                return {
                    "status": "ok",
                    "retcode": 0,
                    "data": {"message_id": f"mock_{adapter_instance._message_seq}"},
                    "message_id": f"mock_{adapter_instance._message_seq}",
                    "message": "ok",
                    "echo": None,
                }

            try:
                return asyncio.create_task(_record())
            except RuntimeError:
                return asyncio.ensure_future(_record())

    async def start(self):
        """测试适配器无需启动（保持空实现以满足 BaseAdapter 契约）"""

    async def shutdown(self):
        """测试适配器无需关闭（保持空实现以满足 BaseAdapter 契约）"""

    async def call_api(self, endpoint: str, **params) -> dict[str, Any]:
        """
        记录并响应 API 调用（返回标准成功响应）

        :param endpoint: API 端点名
        :param params: API 参数
        :return: 标准响应 dict
        """
        self._message_seq += 1
        return {
            "status": "ok",
            "retcode": 0,
            "data": {"echo": params, "endpoint": endpoint},
            "message_id": f"mock_{self._message_seq}",
            "message": "ok",
            "echo": None,
        }

    # ==================== 断言辅助 ====================

    @property
    def last_sent(self) -> SentMessage | None:
        """最近一次出站消息（无出站时为 None）"""
        return self.sent[-1] if self.sent else None

    def clear(self) -> None:
        """清空出站记录"""
        self.sent.clear()
