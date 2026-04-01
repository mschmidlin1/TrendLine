import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from src.base.datetime_utils import (
    convert_series_to_display_tz,
    naive_local_to_utc,
    to_display_timezone,
)


class TestNaiveLocalToUtc(unittest.TestCase):
    def test_naive_roundtrip_instant(self):
        naive = datetime(2026, 7, 15, 14, 30, 0)
        utc_dt = naive_local_to_utc(naive)
        self.assertEqual(utc_dt.tzinfo, timezone.utc)
        self.assertEqual(utc_dt.timestamp(), naive.timestamp())

    def test_aware_normalized_to_utc(self):
        et = ZoneInfo("America/New_York")
        aware = datetime(2026, 7, 15, 10, 0, 0, tzinfo=et)
        utc_dt = naive_local_to_utc(aware)
        self.assertEqual(utc_dt.tzinfo, timezone.utc)
        self.assertEqual(utc_dt, aware.astimezone(timezone.utc))


class TestToDisplayTimezone(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(to_display_timezone(None, ZoneInfo("America/New_York")))

    def test_utc_to_eastern_winter(self):
        tz = ZoneInfo("America/New_York")
        utc = datetime(2026, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        local = to_display_timezone(utc, tz)
        self.assertEqual(local.hour, 13)
        self.assertEqual(local.minute, 0)

    def test_naive_treated_as_utc_wall(self):
        tz = ZoneInfo("America/New_York")
        naive = datetime(2026, 7, 15, 18, 0, 0)
        local = to_display_timezone(naive, tz)
        self.assertEqual(local.tzinfo, tz)


class TestConvertSeriesToDisplayTz(unittest.TestCase):
    def test_preserves_na_and_none(self):
        s = pd.Series([None, pd.NA, datetime(2026, 1, 15, 18, 0, 0, tzinfo=timezone.utc)])
        out = convert_series_to_display_tz(s, "America/New_York")
        self.assertTrue(pd.isna(out.iloc[0]))
        self.assertTrue(pd.isna(out.iloc[1]))
        self.assertIsNotNone(out.iloc[2])


if __name__ == "__main__":
    unittest.main()
