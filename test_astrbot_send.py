"""AstrBot 发送适配：图片、语音与转发在两种平台下的组件差异。"""
from __future__ import annotations

import base64
from pathlib import Path
import tempfile
import unittest

try:
    import astrbot.api.message_components as Comp
    from .main import AstrBotSend, OngekiGachaStar, _mention_identity
except ModuleNotFoundError as exc:
    if exc.name != 'astrbot':
        raise
    Comp = None
    AstrBotSend = OngekiGachaStar = _mention_identity = None

from .growth_commands import request_identity


class _FakeEvent:
    def __init__(self, platform: str) -> None:
        self._platform = platform
        self.sent = []

    def get_platform_name(self) -> str:
        return self._platform

    async def send(self, chain) -> None:
        self.sent.append(chain)


class _FakeStar:
    def __init__(self, platform: str, data_dir: Path) -> None:
        self.event = _FakeEvent(platform)
        self.data_dir = data_dir

    def current_event(self):
        return self.event

    async def _send_chain(self, chain) -> bool:
        await self.event.send(chain)
        return True


class _FakeMention:
    """模拟 botpy 的 mention 对象（群消息只有 member_openid）。"""

    def __init__(self, **fields: object) -> None:
        self.__dict__.update(fields)


class _FakeRawMessage:
    def __init__(self, mentions: list) -> None:
        self.mentions = mentions


class _FakeMessageObj:
    def __init__(self, mentions: list) -> None:
        self.raw_message = _FakeRawMessage(mentions)


class _FakeIncomingEvent:
    def __init__(self, chain: list, mentions: list, self_id: str = "qq_official") -> None:
        self._chain = chain
        self.message_obj = _FakeMessageObj(mentions)
        self._self_id = self_id

    def get_self_id(self) -> str:
        return self._self_id

    def get_messages(self) -> list:
        return self._chain


@unittest.skipIf(Comp is None, '需要 AstrBot 框架环境')
class MentionComponentTests(unittest.TestCase):
    def test_handler_kwargs_carry_message_id_for_growth_transactions(self):
        """养成/语音交易需要幂等键，缺少消息ID会直接拒绝执行。"""

        class _Msg:
            message_id = "MSG-123"

        class _Event:
            unified_msg_origin = "a123:GroupMessage:456"
            message_obj = _Msg()
            message_id = "MSG-123"

            def get_sender_id(self):
                return "openid-user"

            def get_platform_name(self):
                return "qq_official"

        kwargs = OngekiGachaStar._handler_kwargs(_Event(), "/伙伴 1310", {}, [])
        self.assertEqual(kwargs["message_id"], "MSG-123")
        self.assertEqual(kwargs["platform"], "qq_official")
        self.assertEqual(kwargs["message"]["message_id"], "MSG-123")
        self.assertTrue(request_identity(kwargs, kwargs["stream_id"]))

    def test_handler_kwargs_falls_back_when_platform_hides_id(self):
        class _Msg:
            message_id = ""

        class _Event:
            unified_msg_origin = "a123:GroupMessage:456"
            message_obj = _Msg()
            message_id = ""

            def get_sender_id(self):
                return "openid-user"

            def get_platform_name(self):
                return "qq_official"

        kwargs = OngekiGachaStar._handler_kwargs(_Event(), "/伙伴 1310", {}, [])
        self.assertTrue(kwargs["message_id"])
        self.assertTrue(request_identity(kwargs, kwargs["stream_id"]))

    def test_group_member_openid_becomes_target(self):
        """QQ 官方群消息的 @ 成员只有 member_openid，必须被识别成目标。"""
        event = _FakeIncomingEvent(
            [Comp.At(qq="qq_official")],
            [_FakeMention(member_openid="MEMBER-OPENID")],
        )
        self.assertEqual(
            OngekiGachaStar._at_components(event),
            [{"type": "at", "data": {"target_user_id": "MEMBER-OPENID"}}],
        )

    def test_self_and_placeholder_mentions_are_ignored(self):
        event = _FakeIncomingEvent(
            [Comp.At(qq="qq_official")],
            [
                _FakeMention(member_openid=None),
                _FakeMention(member_openid="qq_official"),
                _FakeMention(member_openid="all"),
            ],
        )
        self.assertEqual(OngekiGachaStar._at_components(event), [])

    def test_mention_helper_reads_dict_and_object_shapes(self):
        self.assertEqual(
            _mention_identity({"member_openid": "abc"}), ("abc", False)
        )
        self.assertEqual(
            _mention_identity(_FakeMention(id="123", is_you=True)), ("123", True)
        )
        self.assertEqual(_mention_identity(_FakeMention(member_openid=None)), ("", False))


@unittest.skipIf(Comp is None, '需要 AstrBot 框架环境')
class SendAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make(self, platform: str) -> AstrBotSend:
        return AstrBotSend(_FakeStar(platform, self.data_dir))

    async def test_image_sends_image_component(self):
        send = self.make("qq_official")
        await send.image(base64.b64encode(b"fake-png").decode())
        chain = send._star.event.sent[-1]
        self.assertTrue(any(isinstance(part, Comp.Image) for part in chain.chain))

    async def test_send_results_report_success(self):
        """命令层用返回值判断是否需要补发文字，返回 None 会导致重复消息。"""
        send = self.make("qq_official")
        image = await send.image(base64.b64encode(b"fake-png").decode())
        self.assertTrue(isinstance(image, dict) and image.get("success"))
        text = await send.text("hello")
        self.assertTrue(isinstance(text, dict) and text.get("success"))
        voice = await send.custom("voice", base64.b64encode(b"RIFF....WAVE").decode())
        self.assertTrue(isinstance(voice, dict) and voice.get("success"))
        unknown = await send.custom("unknown", "data")
        self.assertEqual(unknown, {"success": False})

    async def test_voice_uses_record_on_both_platforms(self):
        for platform in ("aiocqhttp", "qq_official"):
            send = self.make(platform)
            await send.custom("voice", base64.b64encode(b"RIFF....WAVE").decode())
            chain = send._star.event.sent[-1]
            self.assertTrue(
                any(isinstance(part, Comp.Record) for part in chain.chain),
                platform,
            )
            records = [part for part in chain.chain if isinstance(part, Comp.Record)]
            self.assertTrue(records[0].file)

    async def test_unknown_custom_type_is_ignored(self):
        send = self.make("aiocqhttp")
        await send.custom("unknown", "data")
        self.assertEqual(send._star.event.sent, [])

    async def test_forward_markdown_on_qq_official_and_nodes_on_onebot(self):
        nodes = [
            {
                "user_id": "123456",
                "nickname": "音击抽卡模拟器",
                "segments": [{"type": "text", "data": "第一行"}],
            }
        ]
        official = self.make("qq_official")
        await official.forward(nodes)
        official_chain = official._star.event.sent[-1]
        self.assertTrue(
            any(
                isinstance(part, Comp.Plain) and "第一行" in part.text
                for part in official_chain.chain
            )
        )

        onebot = self.make("aiocqhttp")
        await onebot.forward(nodes)
        onebot_chain = onebot._star.event.sent[-1]
        self.assertTrue(
            any(isinstance(part, Comp.Nodes) for part in onebot_chain.chain)
        )


if __name__ == "__main__":
    unittest.main()
