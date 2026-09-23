"""QQ 官方 openid 与数字 QQ 的绑定、档案合并测试。"""
from pathlib import Path
import tempfile
import unittest

from .gacha_core import load_cards
from .gacha_db import GachaDatabase
from .growth_catalog import GrowthCatalog
from .growth_migration import change_item
from .plugin import OngekiGachaPlugin


class IdentityBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parent
        cls.cards = load_cards(root / "assets/card_data/card_info_merged.json")
        cls.catalog = GrowthCatalog(root / "assets/growth", cls.cards)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = GachaDatabase(Path(self.temp.name) / "test.db")
        self.db.open()
        self.db.initialize_growth(
            self.cards, enabled=True, rules=self.catalog.rules
        )

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_bind_merges_player_data_and_keeps_alias(self):
        card = next(
            c
            for c in self.cards.cards
            if c.character_id == 1000 and c.rarity == "SSR"
        )
        self.db.commit_draw("123456", [(card.id, card.rarity)], cost=0)
        self.db.grant_points("admin", "123456", 500)
        conn = self.db._conn
        conn.execute("BEGIN IMMEDIATE")
        change_item(conn, "123456", "gift_small", 3)
        conn.execute(
            "UPDATE player_characters SET affection_points=900 "
            "WHERE qq_id='123456' AND character_id=1000"
        )
        conn.commit()

        ok, message = self.db.bind_identity("openid-abc", "123456")
        self.assertTrue(ok, message)
        self.assertEqual(self.db.resolve_identity("123456"), "openid-abc")
        self.assertEqual(self.db.get_bound_qq("openid-abc"), "123456")
        self.assertEqual(self.db.get_player("openid-abc").points, 500)
        inventory_ids = {
            row.card_id for row in self.db.get_inventory("openid-abc")
        }
        self.assertIn(card.id, inventory_ids)
        self.assertGreaterEqual(len(inventory_ids), 1)
        items = conn.execute(
            "SELECT quantity FROM player_items "
            "WHERE qq_id='openid-abc' AND item_id='gift_small'"
        ).fetchone()
        self.assertEqual(int(items[0]), 3)
        affection = conn.execute(
            "SELECT affection_points FROM player_characters "
            "WHERE qq_id='openid-abc' AND character_id=1000"
        ).fetchone()
        self.assertGreaterEqual(int(affection[0]), 900)
        self.assertIsNone(
            conn.execute("SELECT 1 FROM players WHERE qq_id='123456'").fetchone()
        )

    def test_bind_keeps_new_13_state(self):
        self.db.get_player("123456")
        conn = self.db._conn
        conn.execute(
            "INSERT INTO ultimate_completed_charts VALUES(?, ?, ?, ?, ?)",
            ("123456", "ongeki", "song", 3, "2026-09-23"),
        )
        conn.execute(
            "INSERT INTO pending_card_reveals(qq_id,card_id,before_copies,after_copies,created_at) "
            "VALUES(?,?,?,?,?)",
            ("123456", 100001, 0, 1, "2026-09-23"),
        )
        conn.execute(
            "INSERT INTO player_cooldowns VALUES(?, ?, ?)",
            ("123456", "bloom_ticket", "2026-09-23"),
        )
        self.assertTrue(self.db.bind_identity("openid-abc", "123456")[0])
        for table in ("ultimate_completed_charts", "pending_card_reveals", "player_cooldowns"):
            self.assertEqual(
                conn.execute(f"SELECT COUNT(*) FROM {table} WHERE qq_id='openid-abc'").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(f"SELECT COUNT(*) FROM {table} WHERE qq_id='123456'").fetchone()[0],
                0,
            )

    def test_alias_rebinding_merges_into_canonical_account(self):
        self.db.get_player("user-a")
        self.assertTrue(self.db.bind_identity("user-a", "111111")[0])
        self.db.grant_points("admin", "user-b", 300)
        conn = self.db._conn
        conn.execute("BEGIN IMMEDIATE")
        change_item(conn, "user-b", "gift_small", 2)
        conn.commit()
        ok, message = self.db.bind_identity("user-b", "111111")
        self.assertTrue(ok, message)
        self.assertEqual(self.db.resolve_account("user-b"), "user-a")
        self.assertEqual(self.db.resolve_account("111111"), "user-a")
        self.assertEqual(self.db.get_bound_qq("user-b"), "111111")
        self.assertEqual(self.db.get_player("user-a").points, 300)
        quantity = conn.execute(
            "SELECT quantity FROM player_items "
            "WHERE qq_id='user-a' AND item_id='gift_small'"
        ).fetchone()
        self.assertEqual(int(quantity[0]), 2)
        self.assertIsNone(
            conn.execute("SELECT 1 FROM players WHERE qq_id='user-b'").fetchone()
        )

    def test_admin_and_account_share_across_two_bots(self):
        plugin = OngekiGachaPlugin()
        plugin._db = self.db
        plugin.set_plugin_config(plugin.build_default_config())
        plugin.config.admin.admin_ids = ["111111"]
        self.assertTrue(self.db.bind_identity("openid-bot-a", "111111")[0])
        self.assertTrue(self.db.bind_identity("openid-bot-b", "111111")[0])
        self.assertTrue(plugin._is_admin("openid-bot-a"))
        self.assertTrue(plugin._is_admin("openid-bot-b"))
        self.assertEqual(
            plugin._user_id({"user_id": "openid-bot-b"}), "openid-bot-a"
        )
        self.assertEqual(
            plugin._display_user_id("openid-bot-b"), "111111"
        )

    def test_grant_accepts_mention_component_without_placeholder(self):
        plugin = OngekiGachaPlugin()
        plugin._db = self.db
        plugin.set_plugin_config(plugin.build_default_config())
        kwargs = {
            "text": "/奖励 100",
            "matched_groups": {},
            "message": {
                "raw_message": [
                    {"type": "at", "data": {"target_user_id": "TARGET-OPENID"}}
                ]
            },
        }
        parsed = plugin._parse_grant(kwargs)
        self.assertIsNotNone(parsed)
        target, amount, _note = parsed
        self.assertEqual(target, "TARGET-OPENID")
        self.assertEqual(amount, 100)

    def test_grant_accepts_inline_official_mention(self):
        plugin = OngekiGachaPlugin()
        plugin._db = self.db
        plugin.set_plugin_config(plugin.build_default_config())
        kwargs = {
            "text": "/奖励 <@!TARGET-OPENID> 100",
            "matched_groups": {
                "target_at": "<@!TARGET-OPENID>",
                "amount": "100",
                "note": "",
            },
            "message": {
                "raw_message": [
                    {"type": "at", "data": {"target_user_id": "TARGET-OPENID"}}
                ]
            },
        }
        parsed = plugin._parse_grant(kwargs)
        self.assertIsNotNone(parsed)
        target, amount, _note = parsed
        self.assertEqual(target, "TARGET-OPENID")
        self.assertEqual(amount, 100)

    def test_grant_pattern_allows_missing_text_target(self):
        """QQ 官方群消息正文里的 @ 会被清空，只剩 /奖励 10。"""
        pattern = OngekiGachaPlugin.handle_grant_points._mai_command["pattern"]
        match = pattern.match("/奖励  10")
        self.assertIsNotNone(match)
        self.assertEqual(match.group("amount"), "10")
        self.assertIsNone(match.group("target_id"))
        self.assertIsNone(match.group("target_at"))

        numbered = pattern.match("/奖励 3130274394 10")
        self.assertEqual(numbered.group("target_id"), "3130274394")
        self.assertEqual(numbered.group("amount"), "10")

        noted = pattern.match("/奖励 10 备注")
        self.assertEqual(noted.group("amount"), "10")
        self.assertEqual(noted.group("note"), "备注")
        self.assertIsNone(noted.group("target_id"))

        mentioned = pattern.match("/奖励 @123456 100")
        self.assertEqual(mentioned.group("target_at"), "@123456")
        self.assertEqual(mentioned.group("amount"), "100")

    def test_grant_without_text_target_uses_mention_component(self):
        plugin = OngekiGachaPlugin()
        plugin._db = self.db
        plugin.set_plugin_config(plugin.build_default_config())
        pattern = OngekiGachaPlugin.handle_grant_points._mai_command["pattern"]
        text = "/奖励  10"
        match = pattern.match(text)
        kwargs = {
            "text": text,
            "matched_groups": match.groupdict(),
            "message": {
                "raw_message": [
                    {"type": "at", "data": {"target_user_id": "TARGET-OPENID"}}
                ]
            },
        }
        parsed = plugin._parse_grant(kwargs)
        self.assertIsNotNone(parsed)
        target, amount, _note = parsed
        self.assertEqual(target, "TARGET-OPENID")
        self.assertEqual(amount, 10)

    def test_grant_note_kept_when_target_comes_from_component(self):
        plugin = OngekiGachaPlugin()
        plugin._db = self.db
        plugin.set_plugin_config(plugin.build_default_config())
        pattern = OngekiGachaPlugin.handle_grant_points._mai_command["pattern"]
        text = "/奖励  10 补偿"
        kwargs = {
            "text": text,
            "matched_groups": pattern.match(text).groupdict(),
            "message": {
                "raw_message": [
                    {"type": "at", "data": {"target_user_id": "TARGET-OPENID"}}
                ]
            },
        }
        parsed = plugin._parse_grant(kwargs)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[1], 10)
        self.assertEqual(parsed[2], "补偿")

    def test_grant_without_target_returns_usage(self):
        """只有机器人自己的 @ 占位时不能瞎猜目标。"""
        plugin = OngekiGachaPlugin()
        plugin._db = self.db
        plugin.set_plugin_config(plugin.build_default_config())
        pattern = OngekiGachaPlugin.handle_grant_points._mai_command["pattern"]
        text = "/奖励  10"
        kwargs = {
            "text": text,
            "matched_groups": pattern.match(text).groupdict(),
        }
        self.assertIsNone(plugin._parse_grant(kwargs))

    def test_grant_repeated_number_not_split_into_target(self):
        plugin = OngekiGachaPlugin()
        plugin._db = self.db
        plugin.set_plugin_config(plugin.build_default_config())
        pattern = OngekiGachaPlugin.handle_grant_points._mai_command["pattern"]
        kwargs = {
            "text": "/奖励 313027439410",
            "matched_groups": pattern.match("/奖励 313027439410").groupdict(),
        }
        self.assertIsNone(plugin._parse_grant(kwargs))

    def test_plugin_admin_and_display_helpers_use_binding(self):
        plugin = OngekiGachaPlugin()
        plugin._db = self.db
        plugin.set_plugin_config(plugin.build_default_config())
        plugin.config.admin.admin_ids = ["123456"]
        self.db.get_player("123456")
        self.assertTrue(self.db.bind_identity("openid-xyz", "123456")[0])
        self.assertTrue(plugin._is_admin("openid-xyz"))
        self.assertEqual(plugin._display_user_id("openid-xyz"), "123456")
        self.assertIsNone(plugin._binding_hint("openid-xyz"))
        self.assertIn("绑定QQ", plugin._binding_hint("openid-unbound"))
        self.assertIsNone(plugin._binding_hint("123456"))


if __name__ == "__main__":
    unittest.main()
