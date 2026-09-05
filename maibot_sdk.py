"""MaiBot SDK 兼容层（AstrBot 专用）。

原插件面向 MaiBot SDK 编写，这里提供一组最小兼容实现：

- :class:`PluginConfigBase`：基于 pydantic v2 的强类型配置基类；
- :class:`MaiBotPlugin`：承载 ``ctx`` / ``config`` 与生命周期方法的业务基类；
- :func:`Command`：把命令元数据挂在函数对象上，由 ``main.py`` 统一分发。

AstrBot 加载本插件时会优先导入本目录下的 ``maibot_sdk``，因此原插件
``config_model.py`` / ``plugin.py`` 可以基本保持不变。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

import pydantic


class PluginConfigBase(pydantic.BaseModel):
    """强类型配置基类（pydantic v2）。"""

    model_config = {
        "extra": "ignore",
        "arbitrary_types_allowed": True,
    }


def Field(*args: Any, **kwargs: Any) -> Any:
    """转发 pydantic 的 Field，保持原插件导入方式不变。"""
    return pydantic.Field(*args, **kwargs)


def Command(
    name: str,
    description: str = "",
    pattern: Optional[str] = None,
    aliases: Optional[list[str]] = None,
) -> Callable:
    """标记一个命令处理器。

    用正则 ``pattern`` 匹配整条消息，命中后由 ``main.py`` 把 ``stream_id``、
    ``matched_groups``、``user_id``、``message`` 等参数传给 handler。
    ``aliases`` 仅保留展示用途，实际匹配仍以 ``pattern`` 为准。
    """

    def decorator(func: Callable) -> Callable:
        func._mai_command = {
            "name": name,
            "description": description,
            "pattern": re.compile(pattern) if pattern else None,
            "aliases": list(aliases or []),
        }
        return func

    return decorator


class MaiBotPlugin:
    """核心插件基类：承载 ctx / config 与生命周期。"""

    config_model: Any = None

    def __init__(self) -> None:
        self.ctx: Any = None
        self.config: Any = None

    async def on_load(self) -> None:
        """插件加载时调用。"""

    async def on_unload(self) -> None:
        """插件卸载时调用。"""
