from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .gacha_db import GachaDatabase
from .plugin import OngekiGachaPlugin


class TimeBoundaryTests(unittest.TestCase):
    def test_china_midnight_changes_daily_date_and_scheduler(self):
        before = datetime(2026, 9, 23, 15, 59, 59, tzinfo=timezone.utc)
        after = datetime(2026, 9, 23, 16, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(GachaDatabase.current_date_str(8, now_utc=before), '2026-09-23')
        self.assertEqual(GachaDatabase.current_date_str(8, now_utc=after), '2026-09-24')
        self.assertEqual(GachaDatabase.current_date_str(0, now_utc=after), '2026-09-23')
        self.assertEqual(OngekiGachaPlugin._seconds_until_next_reset(8, now_utc=before), 1.0)
        self.assertEqual(OngekiGachaPlugin._seconds_until_next_reset(8, now_utc=after), 86400.0)

    def test_weekly_reset_uses_local_thursday_and_does_not_rewind(self):
        before = datetime(2026, 9, 23, 15, 59, 59, tzinfo=timezone.utc)
        after = datetime(2026, 9, 23, 16, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(GachaDatabase._weekly_5_key(8, now_utc=before), '2026-09-17')
        self.assertEqual(GachaDatabase._weekly_5_key(8, now_utc=after), '2026-09-24')
        with tempfile.TemporaryDirectory() as temp:
            db = GachaDatabase(Path(temp) / 'state.db')
            db.open()
            try:
                db.get_player('u')
                db._conn.execute(
                    "UPDATE players SET weekly_5_guarantee_week='2026-09-24', "
                    "weekly_5_guarantee_used=1 WHERE qq_id='u'"
                )
                with patch.object(GachaDatabase, 'current_date_str', return_value='2026-09-23'), \
                     patch.object(GachaDatabase, '_weekly_5_key', return_value='2026-09-17'):
                    self.assertEqual(db.sync_time_based_state(tz_offset_hours=8), (0, 0))
                    self.assertFalse(db.weekly_5_guarantee_available('u', tz_offset_hours=8))
                    self.assertFalse(db.claim_weekly_5_guarantee('u', tz_offset_hours=8))
                row = db._conn.execute(
                    'SELECT weekly_5_guarantee_week,weekly_5_guarantee_used '
                    "FROM players WHERE qq_id='u'"
                ).fetchone()
                self.assertEqual(tuple(row), ('2026-09-24', 1))
            finally:
                db.close()

    def test_checkin_rejects_future_record_after_clock_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            db = GachaDatabase(Path(temp) / 'state.db')
            db.open()
            try:
                db.get_player('u')
                db._conn.execute(
                    "UPDATE players SET last_checkin_date='2026-09-24', "
                    "streak_days=7 WHERE qq_id='u'"
                )
                with patch.object(GachaDatabase, 'current_date_str', return_value='2026-09-23'):
                    receipt = db.daily_checkin(
                        'u', min_reward=70, max_reward=70,
                        streak_daily_step=10, streak_daily_max=100,
                        streak_weekly_reward=600, streak_cycle_days=15,
                        streak_cycle_reward=1200, monthly_daily_bonus=80,
                        tz_offset_hours=8,
                    )
                self.assertFalse(receipt.success)
                self.assertIn('服务器时间', receipt.error)
                self.assertEqual(db.get_player('u').streak_days, 7)
            finally:
                db.close()

    def test_monthly_remaining_is_never_negative(self):
        self.assertEqual(GachaDatabase.monthly_card_remaining_days('2026-09-20', '2026-09-23'), 0)


if __name__ == '__main__':
    unittest.main()
