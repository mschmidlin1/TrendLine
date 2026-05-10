"""Tests for timing category classification (news trades PnL buckets)."""
from __future__ import annotations

import unittest
from zoneinfo import ZoneInfo

import pandas as pd

from src.front_end.charts.timing_category import (
    TIMING_CAT_1,
    TIMING_CAT_2,
    TIMING_CAT_3,
    TIMING_CAT_4,
    TIMING_CAT_5,
    TIMING_CAT_6,
    TIMING_OTHER,
    classify_timing_category_row,
    prepare_completed_trades_for_timing,
)
from src.configs import DISPLAY_TIMEZONE_NAME


def _ts(d: tuple[int, int, int], h: int, m: int = 0, et: ZoneInfo | None = None) -> pd.Timestamp:
    if et is None:
        et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    y, mo, day = d
    return pd.Timestamp(year=y, month=mo, day=day, hour=h, minute=m, tz=et)


class TimingCategoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.et = ZoneInfo(DISPLAY_TIMEZONE_NAME)

    def test_cat1_open_recent_article_band_same_day(self) -> None:
        day = (2025, 5, 7)
        art = _ts(day, 9, 15, self.et)
        buy = _ts(day, 9, 35, self.et)
        sell = _ts(day, 15, 0, self.et)
        self.assertEqual(
            classify_timing_category_row(art, buy, sell, self.et),
            TIMING_CAT_1,
        )

    def test_cat2_off_hours_recent_within_8h(self) -> None:
        day = (2025, 5, 7)
        art = _ts(day, 8, 0, self.et)
        buy = _ts(day, 9, 35, self.et)
        sell = _ts(day, 14, 0, self.et)
        self.assertEqual(
            classify_timing_category_row(art, buy, sell, self.et),
            TIMING_CAT_2,
        )

    def test_cat2_exactly_8h_delta_inclusive(self) -> None:
        day = (2025, 5, 7)
        art = _ts(day, 1, 35, self.et)
        buy = _ts(day, 9, 35, self.et)
        sell = _ts(day, 12, 0, self.et)
        self.assertEqual(
            classify_timing_category_row(art, buy, sell, self.et),
            TIMING_CAT_2,
        )

    def test_cat3_off_hours_stale_over_8h(self) -> None:
        art = _ts((2025, 5, 5), 13, 0, self.et)
        buy = _ts((2025, 5, 7), 9, 35, self.et)
        sell = _ts((2025, 5, 7), 14, 0, self.et)
        self.assertEqual(
            classify_timing_category_row(art, buy, sell, self.et),
            TIMING_CAT_3,
        )

    def test_cat4_inday_scalp(self) -> None:
        day = (2025, 5, 7)
        art = _ts(day, 10, 0, self.et)
        buy = _ts(day, 10, 15, self.et)
        sell = _ts(day, 15, 0, self.et)
        self.assertEqual(
            classify_timing_category_row(art, buy, sell, self.et),
            TIMING_CAT_4,
        )

    def test_cat5_overnight_next_weekday_open(self) -> None:
        art = _ts((2025, 5, 8), 14, 30, self.et)
        buy = _ts((2025, 5, 8), 15, 0, self.et)
        sell = _ts((2025, 5, 9), 9, 35, self.et)
        self.assertEqual(
            classify_timing_category_row(art, buy, sell, self.et),
            TIMING_CAT_5,
        )

    def test_cat6_friday_to_monday_afternoon(self) -> None:
        art = _ts((2025, 5, 9), 14, 30, self.et)
        buy = _ts((2025, 5, 9), 15, 0, self.et)
        sell = _ts((2025, 5, 12), 14, 0, self.et)
        self.assertEqual(
            classify_timing_category_row(art, buy, sell, self.et),
            TIMING_CAT_6,
        )

    def test_other_slow_reaction_same_day(self) -> None:
        day = (2025, 5, 7)
        art = _ts(day, 9, 0, self.et)
        buy = _ts(day, 14, 0, self.et)
        sell = _ts(day, 15, 30, self.et)
        self.assertEqual(
            classify_timing_category_row(art, buy, sell, self.et),
            TIMING_OTHER,
        )

    def test_prepare_completed_trades_drops_bad_pnl(self) -> None:
        et = self.et
        df = pd.DataFrame(
            {
                "Date (ET)": [_ts((2025, 5, 7), 9, 15, et)],
                "Purchased Date (ET)": [_ts((2025, 5, 7), 9, 35, et)],
                "Sold Date (ET)": [_ts((2025, 5, 7), 15, 0, et)],
                "Total Gain": [float("nan")],
                "invested": [10.0],
            }
        )
        self.assertTrue(prepare_completed_trades_for_timing(df).empty)

    def test_prepare_completed_trades_keeps_valid(self) -> None:
        et = self.et
        df = pd.DataFrame(
            {
                "Date (ET)": [_ts((2025, 5, 7), 9, 15, et)],
                "Purchased Date (ET)": [_ts((2025, 5, 7), 9, 35, et)],
                "Sold Date (ET)": [_ts((2025, 5, 7), 15, 0, et)],
                "Total Gain": [1.23],
                "invested": [10.0],
            }
        )
        self.assertEqual(len(prepare_completed_trades_for_timing(df)), 1)


if __name__ == "__main__":
    unittest.main()
