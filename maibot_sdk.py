"""MaiBot SDK 兼容层。

提供一组最小兼容实现：

- :class:`PluginConfigBase`：基于 pydantic v2 的强类型配置基类；
- :class:`MaiBotPlugin`：承载 ``ctx`` / ``config`` 与生命周期方法的业务基类；
- :func:`Command`：把命令元数据挂在函数对象上，由 ``main.py`` 统一分发。

插件会优先导入本目录下的 ``maibot_sdk``，因此
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

    def _set_context(self, ctx: Any) -> None:
        """兼容 MaiBot 生命周期：注入 ctx。"""
        self.ctx = ctx

    def build_default_config(self) -> dict:
        """返回 config_model 的默认配置字典。"""
        model = self.config_model or PluginConfigBase
        return model().model_dump()

    def set_plugin_config(self, config: dict) -> None:
        """按 config_model 解析并保存插件配置。"""
        model = self.config_model or PluginConfigBase
        self.config = model(**dict(config)) if isinstance(config, dict) else config

    def get_components(self) -> list[dict]:
        """把 ``@Command`` 标记的方法收集成 MaiBot 风格的组件列表。"""
        components: list[dict] = []
        seen: set[str] = set()
        for cls in type(self).__mro__:
            for value in vars(cls).values():
                meta = getattr(value, "_mai_command", None)
                if not isinstance(meta, dict) or not meta.get("pattern"):
                    continue
                name = str(meta.get("name") or getattr(value, "__name__", ""))
                if name in seen:
                    continue
                seen.add(name)
                raw_pattern = meta.get("pattern")
                components.append(
                    {
                        "type": "COMMAND",
                        "metadata": {
                            "name": name,
                            "description": str(meta.get("description") or ""),
                            "command_pattern": (
                                raw_pattern.pattern
                                if hasattr(raw_pattern, "pattern")
                                else str(raw_pattern or "")
                            ),
                            "aliases": list(meta.get("aliases") or []),
                            "handler_name": getattr(value, "__name__", name),
                        },
                    }
                )
        return components

    async def on_load(self) -> None:
        """插件加载时调用。"""

    async def on_unload(self) -> None:
        """插件卸载时调用。"""
