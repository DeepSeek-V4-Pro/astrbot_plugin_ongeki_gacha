"""音击抽卡模拟器。

业务规则全部集中在 ``gacha_*`` 模块与 ``plugin.py`` 中，这里统一完成
命令分发、消息发送、配置与数据目录的接入：

- ``@Command`` 声明里的正则在这里统一匹配并分发；
- ``ctx.send.*`` 与 ``ctx.paths`` 映射到插件事件 / 插件数据目录；
- 图片输出使用 MessageChain 的 base64 / 文件图片能力。
"""

from __future__ import annotations

import contextvars
import os
import re
from pathlib import Path
from typing import Optional

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, StarTools

from .config_model import OngekiGachaPluginConfig
from .plugin import OngekiGachaPlugin

# 命令分发期间持有"当前事件"，供 ctx.send.* 直接回复触发命令的会话。
_current_event: contextvars.ContextVar[Optional[AstrMessageEvent]] = (
    contextvars.ContextVar("ongeki_current_event", default=None)
)

# 用于估计正则"字面前缀"长度，字面前缀越长 = 命令越具体，优先匹配。
_OPERATOR = re.compile(r"(\\.|\(|\)|\[|\]|\.\+?|\*|\?|\{|\}|\||\^|\$)")


def _literal_prefix_len(pattern: str) -> int:
    match = _OPERATOR.search(pattern.lstrip("^"))
    return match.start() if match else len(pattern)


class AstrBotSend:
    """把命令层的 ``ctx.send.text/image/forward`` 映射到 AstrBot 发送。"""

    def __init__(self, star: "OngekiGachaStar") -> None:
        self._star = star

    async def text(self, text: str, stream_id: str = "") -> None:
        del stream_id
        await self._star._send_chain(MessageChain().message(text))

    async def image(self, image: str, stream_id: str = "") -> None:
        """发送图片；参数为 base64 图片、http 链接或本地路径。"""
        del stream_id
        if image.startswith(("http://", "https://")):
            chain = MessageChain().url_image(image)
        elif os.path.isfile(image):
            chain = MessageChain().file_image(image)
        else:
            chain = MessageChain().base64_image(image)
        await self._star._send_chain(chain)

    async def forward(self, nodes: list[dict], stream_id: str = "") -> None:
        """发送合并转发；不支持合并转发的平台降级为结构化文本。"""
        del stream_id
        event = self._star.current_event()
        if event is None:
            logger.warning("forward 调用时缺少当前事件，消息被丢弃")
            return

        platform = event.get_platform_name()
        if platform == "aiocqhttp":
            astr_nodes = []
            for node in nodes or []:
                content = []
                for seg in node.get("segments", []):
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        text_seg = str(seg.get("content") or seg.get("data") or "")
                        content.append(Comp.Plain(text_seg))
                raw_uin = str(node.get("user_id", "0"))
                uin = raw_uin if raw_uin.isdigit() else "0"
                astr_nodes.append(
                    Comp.Node(
                        uin=uin,
                        name=str(node.get("nickname", "")),
                        content=content,
                    )
                )
            chain = MessageChain(chain=[Comp.Nodes(astr_nodes)])
        elif platform in {"qq_official", "qq_official_webhook"}:
            # QQ 官方机器人开放平台没有合并转发接口，改用 Markdown 渲染长内容。
            title = ""
            lines: list[str] = []
            for node in nodes or []:
                nickname = str(node.get("nickname", "")).strip()
                if nickname and not title:
                    title = nickname
                for seg in node.get("segments", []):
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        line = str(seg.get("content") or seg.get("data") or "").strip()
                        if line:
                            lines.append(line)
            body = "\n".join(lines)
            markdown = f"**{title}**\n\n{body}" if title else body
            chain = MessageChain().message(markdown).use_markdown(True)
        else:
            lines = []
            for node in nodes or []:
                nickname = str(node.get("nickname", "")).strip()
                parts = []
                for seg in node.get("segments", []):
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        parts.append(str(seg.get("content") or seg.get("data") or ""))
                body = "\n".join(p for p in parts if p)
                lines.append(f"【{nickname}】\n{body}" if nickname else body)
            chain = MessageChain().message("\n\n".join(lines))
        await self._star._send_chain(chain)


class AstrBotPaths:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.runtime_dir = data_dir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.plugin_dir = Path(__file__).resolve().parent


class AstrBotCtx:
    """命令层 ``self.ctx`` 的 AstrBot 映射。"""

    def __init__(self, star: "OngekiGachaStar") -> None:
        self.send = AstrBotSend(star)
        self.paths = AstrBotPaths(star.data_dir)
        self.logger = logger


class OngekiGachaStar(Star):
    """音击抽卡模拟器。"""

    def __init__(
        self,
        context: Context,
        config: AstrBotConfig | None = None,
    ) -> None:
        super().__init__(context)

        raw: dict = dict(config) if config is not None else {}
        try:
            parsed = OngekiGachaPluginConfig(**raw)
        except Exception as exc:  # pragma: no cover - 配置异常时兜底
            logger.warning("音击抽卡配置解析失败，使用默认配置: %s", exc)
            parsed = OngekiGachaPluginConfig()

        self.data_dir = Path(
            StarTools.get_data_dir(
                getattr(self, "name", None) or "astrbot_plugin_ongeki_gacha"
            )
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._inner = OngekiGachaPlugin()
        self._inner.ctx = AstrBotCtx(self)
        self._inner.config = parsed

        self._commands: list[dict] = self._collect_commands()

    # ---- 生命周期 ----

    async def initialize(self) -> None:
        await self._inner.on_load()

    async def terminate(self) -> None:
        await self._inner.on_unload()

    async def on_config_update(
        self,
        scope: str,
        config_data: dict[str, object],
        version: str,
    ) -> None:
        """配置变化时热更新业务资源。"""
        if scope != "self":
            return
        raw: dict = dict(config_data) if isinstance(config_data, dict) else {}
        try:
            parsed = OngekiGachaPluginConfig(**raw)
        except Exception as exc:
            logger.warning("音击抽卡配置热更新解析失败，保留旧配置: %s", exc)
            return
        self._inner.config = parsed
        await self._inner.on_config_update(scope, raw, version)

    # ---- 命令收集与分发 ----

    @staticmethod
    def _iter_handlers():
        for cls in OngekiGachaPlugin.__mro__:
            for value in vars(cls).values():
                if callable(value) and getattr(value, "_mai_command", None):
                    yield value

    def _collect_commands(self) -> list[dict]:
        commands = []
        for func in self._iter_handlers():
            meta = func._mai_command
            if meta.get("pattern") is None:
                continue
            commands.append(
                {
                    "meta": meta,
                    "alias_patterns": [
                        re.compile(
                            r"^" + re.escape(str(alias).strip()) + r"(?:[ \t]+.*)?$"
                        )
                        for alias in (meta.get("aliases") or [])
                        if str(alias).strip()
                    ],
                    # 把类上的函数绑定到插件实例（否则调用时缺少 self）。
                    "handler": func.__get__(self._inner, type(self._inner)),
                }
            )
        # 字面前缀越长（静态文本越多）的命令越具体，优先匹配。
        commands.sort(
            key=lambda c: (
                -_literal_prefix_len(c["meta"]["pattern"].pattern),
                -len(c["meta"]["pattern"].pattern),
            )
        )
        return commands

    def current_event(self) -> Optional[AstrMessageEvent]:
        return _current_event.get()

    @staticmethod
    def _at_components(event: AstrMessageEvent) -> list[dict]:
        """把 AstrBot 消息链中的 @ 段转换成原插件能识别的原始组件。"""
        result: list[dict] = []
        self_id = str(event.get_self_id() or "")
        try:
            for component in event.get_messages() or []:
                if not hasattr(component, "qq"):
                    continue
                qq = getattr(component, "qq", "")
                qq = str(qq or "").strip()
                if qq and qq not in {"all", "qq_official"} and qq != self_id:
                    result.append(
                        {
                            "type": "at",
                            "data": {"target_user_id": qq},
                        }
                    )
        except Exception:
            logger.debug("读取 AstrBot @ 消息组件失败", exc_info=True)
        try:
            raw_message = getattr(event.message_obj, "raw_message", None)
            mentions = getattr(raw_message, "mentions", None) or []
            for mention in mentions:
                if getattr(mention, "is_you", False):
                    continue
                mention_id = str(
                    getattr(mention, "id", None)
                    or getattr(mention, "user_id", None)
                    or ""
                ).strip()
                if not mention_id or mention_id == self_id:
                    continue
                result.append(
                    {
                        "type": "at",
                        "data": {"target_user_id": mention_id},
                    }
                )
        except Exception:
            logger.debug("读取 AstrBot 原始 @ mention 失败", exc_info=True)
        return result

    @staticmethod
    def _image_components(event: AstrMessageEvent) -> list[dict]:
        """把 AstrBot 消息链中的图片段转换成原插件能识别的原始组件。"""
        result: list[dict] = []
        try:
            image_type = getattr(
                getattr(Comp, "ComponentType", None),
                "Image",
                None,
            )
            for component in event.get_messages() or []:
                component_type = getattr(component, "type", None)
                if (
                    image_type is not None
                    and component_type != image_type
                    and not str(component_type or "").lower().endswith("image")
                ):
                    continue
                if image_type is None and not str(
                    component_type or ""
                ).lower().endswith("image"):
                    continue
                result.append(
                    {
                        "type": "image",
                        "url": str(getattr(component, "url", "") or ""),
                        "file": str(getattr(component, "file", "") or ""),
                        "path": str(getattr(component, "path", "") or ""),
                    }
                )
        except Exception:
            logger.debug("读取 AstrBot 图片消息组件失败", exc_info=True)
        return result

    async def _send_chain(self, chain: MessageChain) -> None:
        event = self.current_event()
        if event is None:
            logger.warning("缺少当前事件，无法发送消息")
            return
        try:
            await event.send(chain)
        except Exception:
            logger.exception("发送消息失败")

    @filter.event_message_type(filter.EventMessageType.ALL, priority=5)
    async def on_message(self, event: AstrMessageEvent) -> None:
        if self._inner is None:
            return
        text = (event.message_str or "").strip()
        if not text:
            return
        # AstrBot 的 wake_prefix（默认含 "/"）唤醒后可能会把消息开头的 "/"
        # 剥掉，导致 "/签到" 变成 "签到"。命令正则统一以 "/" 开头，这里补回。
        if not text.startswith("/"):
            text = "/" + text

        for cmd in self._commands:
            match = cmd["meta"]["pattern"].match(text)
            alias_match = None
            if not match:
                for alias_pattern in cmd["alias_patterns"]:
                    alias_match = alias_pattern.match(text)
                    if alias_match:
                        break
            if not match and alias_match is None:
                continue

            token = _current_event.set(event)
            try:
                await cmd["handler"](
                    stream_id=event.unified_msg_origin,
                    matched_groups=match.groupdict() if match else {},
                    user_id=event.get_sender_id(),
                    text=text,
                    message={
                        "message_info": {
                            "user_info": {"user_id": event.get_sender_id()}
                        },
                        "raw_message": (
                            self._at_components(event)
                            + self._image_components(event)
                        ),
                    },
                )
            except Exception:
                logger.exception("命令 %s 处理失败", cmd["meta"]["name"])
            finally:
                _current_event.reset(token)

            event.stop_event()
            return
