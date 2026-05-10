"""
Timing buckets for PnL-by-strategy chart (news trades table).

Classification rules follow docs/plan: US/Eastern session windows, priority Cat1..Cat6 then Other.
"""
from __future__ import annotations

from datetime import date, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.configs import DISPLAY_TIMEZONE_NAME, MARKET_HOLD_TIME

COL_ARTICLE: Final = "Date (ET)"
COL_BUY: Final = "Purchased Date (ET)"
COL_SELL: Final = "Sold Date (ET)"
COL_GAIN: Final = "Total Gain"
COL_INVESTED: Final = "invested"

OFF_HOURS_RECENT_HOURS: Final = 8

# Internal keys (stable); UI maps to labels
TIMING_CAT_1: Final = "cat1"
TIMING_CAT_2: Final = "cat2"
TIMING_CAT_3: Final = "cat3"
TIMING_CAT_4: Final = "cat4"
TIMING_CAT_5: Final = "cat5"
TIMING_CAT_6: Final = "cat6"
TIMING_OTHER: Final = "other"

TIMING_CATEGORY_ORDER: Final[tuple[str, ...]] = (
    TIMING_CAT_1,
    TIMING_CAT_2,
    TIMING_CAT_3,
    TIMING_CAT_4,
    TIMING_CAT_5,
    TIMING_CAT_6,
    TIMING_OTHER,
)

TIMING_CATEGORY_LABELS: Final[dict[str, str]] = {
    TIMING_CAT_1: "Open — recent article (9–10AM)",
    TIMING_CAT_2: "Open — off-hours article ≤8h",
    TIMING_CAT_3: "Open — off-hours article >8h",
    TIMING_CAT_4: "In-day buy/sell",
    TIMING_CAT_5: "Overnight — next weekday open",
    TIMING_CAT_6: "Multi-day / delayed exit",
    TIMING_OTHER: "Other",
}

# Short user-facing explanations (table column).
TIMING_CATEGORY_DESCRIPTIONS: Final[dict[str, str]] = {
    TIMING_CAT_1: "Filled buy 9:30–10 AM; article archived 9–10 AM same ET day.",
    TIMING_CAT_2: "Filled buy 9:30–10 AM; article outside 9–10 AM window; ≤8h before buy.",
    TIMING_CAT_3: "Filled buy 9:30–10 AM; article outside 9–10 AM window; >8h before buy.",
    TIMING_CAT_4: "Article during RTH; buy within 30m of article; sold same day by 4 PM.",
    TIMING_CAT_5: "RTH article, quick buy, 4h hold ends after close; sold next weekday 9:30–10 AM.",
    TIMING_CAT_6: "Sell on a later ET day than buy; not the narrow next-open exit.",
    TIMING_OTHER: "Completed trade that does not match categories 1–6.",
}

_T0930 = time(9, 30)
_T1000 = time(10, 0)
_T0900 = time(9, 0)
_T1600 = time(16, 0)


def _is_weekday(d: date) -> bool:
    return d.weekday() < 5


def _to_et(ts: datetime | pd.Timestamp, et: ZoneInfo) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert(et)


def _in_open_purchase_window(buy_et: pd.Timestamp) -> bool:
    if not _is_weekday(buy_et.date()):
        return False
    t = buy_et.time()
    return _T0930 <= t < _T1000


def _article_in_opening_hour_band(art_et: pd.Timestamp) -> bool:
    t = art_et.time()
    return _T0900 <= t < _T1000


def _in_rth(ts: pd.Timestamp) -> bool:
    if not _is_weekday(ts.date()):
        return False
    t = ts.time()
    return _T0930 <= t <= _T1600


def _same_et_calendar_day(a: pd.Timestamp, b: pd.Timestamp) -> bool:
    return a.date() == b.date()


def _off_hours_open_purchase_base(art_et: pd.Timestamp, buy_et: pd.Timestamp) -> bool:
    """Open-window buy and article does not qualify for Cat 1 (same-day 9–10AM band)."""
    if not _in_open_purchase_window(buy_et):
        return False
    cat1_article = _article_in_opening_hour_band(art_et) and _same_et_calendar_day(art_et, buy_et)
    return not cat1_article


def _article_to_buy_delta_seconds(art_et: pd.Timestamp, buy_et: pd.Timestamp) -> float:
    return (buy_et - art_et).total_seconds()


def _buy_within_30m_after_article(art_et: pd.Timestamp, buy_et: pd.Timestamp) -> bool:
    sec = _article_to_buy_delta_seconds(art_et, buy_et)
    return 0 <= sec <= 30 * 60


def _first_weekday_strictly_after(buy_date: date) -> date:
    d = buy_date + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _rth_close_on_date(et: ZoneInfo, d: date) -> pd.Timestamp:
    return pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=16, minute=0, tz=et)


def hold_end_after_rth_close_on_buy_day(buy_et: pd.Timestamp, et: ZoneInfo) -> bool:
    """True if buy_utc + MARKET_HOLD_TIME is strictly after 4:00 PM ET on the buy calendar day."""
    buy_utc = buy_et.tz_convert("UTC")
    hold_end = buy_utc + MARKET_HOLD_TIME
    hold_et = hold_end.tz_convert(et)
    close = _rth_close_on_date(et, buy_et.date())
    return hold_et > close


def _sell_on_buy_day_by_1600(sell_et: pd.Timestamp, buy_et: pd.Timestamp) -> bool:
    if sell_et.date() != buy_et.date():
        return False
    return sell_et.time() <= _T1600


def _sell_in_open_window_on_date(sell_et: pd.Timestamp) -> bool:
    return _in_open_purchase_window(sell_et)


def classify_timing_category_row(
    art_et: pd.Timestamp,
    buy_et: pd.Timestamp,
    sell_et: pd.Timestamp,
    et: ZoneInfo | None = None,
) -> str:
    """
    Assign exactly one timing category (TIMING_CAT_* or TIMING_OTHER).
    Caller must pass completed-trade rows with valid timestamps.
    """
    if et is None:
        et = ZoneInfo(DISPLAY_TIMEZONE_NAME)

    art_et = _to_et(art_et, et)
    buy_et = _to_et(buy_et, et)
    sell_et = _to_et(sell_et, et)

    # --- Cat 1
    if _in_open_purchase_window(buy_et) and _article_in_opening_hour_band(art_et) and _same_et_calendar_day(art_et, buy_et):
        return TIMING_CAT_1

    # --- Cat 2 / 3
    if _off_hours_open_purchase_base(art_et, buy_et):
        delta_sec = _article_to_buy_delta_seconds(art_et, buy_et)
        if delta_sec < 0:
            return TIMING_CAT_2
        if delta_sec <= OFF_HOURS_RECENT_HOURS * 3600:
            return TIMING_CAT_2
        return TIMING_CAT_3

    # --- Cat 4
    if (
        _in_rth(art_et)
        and _buy_within_30m_after_article(art_et, buy_et)
        and _sell_on_buy_day_by_1600(sell_et, buy_et)
    ):
        return TIMING_CAT_4

    # --- Cat 5
    d_next = _first_weekday_strictly_after(buy_et.date())
    if (
        _in_rth(art_et)
        and _in_rth(buy_et)
        and _buy_within_30m_after_article(art_et, buy_et)
        and hold_end_after_rth_close_on_buy_day(buy_et, et)
        and sell_et.date() == d_next
        and _sell_in_open_window_on_date(sell_et)
    ):
        return TIMING_CAT_5

    # --- Cat 6
    if sell_et.date() > buy_et.date():
        return TIMING_CAT_6

    return TIMING_OTHER


def prepare_completed_trades_for_timing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep rows with executed buy/sell, article time, finite Total Gain, and invested > 0 when present.
    """
    if df.empty:
        return df
    need = [COL_ARTICLE, COL_BUY, COL_SELL, COL_GAIN]
    for c in need:
        if c not in df.columns:
            return pd.DataFrame(columns=df.columns)

    work = df.copy()
    buy = pd.to_datetime(work[COL_BUY], errors="coerce", utc=True)
    sell = pd.to_datetime(work[COL_SELL], errors="coerce", utc=True)
    art = pd.to_datetime(work[COL_ARTICLE], errors="coerce", utc=True)
    gain = pd.to_numeric(work[COL_GAIN], errors="coerce")

    ok = buy.notna() & sell.notna() & art.notna()
    g = gain.to_numpy(dtype=float, copy=True)
    ok &= np.isfinite(g)

    if COL_INVESTED in work.columns:
        inv = pd.to_numeric(work[COL_INVESTED], errors="coerce")
        ok &= inv.notna() & (inv > 0)

    return work.loc[ok].copy()


def classify_timing_category_dataframe(df: pd.DataFrame, et: ZoneInfo | None = None) -> pd.Series:
    """Vectorized application via row-wise classify (dataframe is small)."""
    if et is None:
        et = ZoneInfo(DISPLAY_TIMEZONE_NAME)

    def _one_row(row: pd.Series) -> str:
        return classify_timing_category_row(
            row[COL_ARTICLE],
            row[COL_BUY],
            row[COL_SELL],
            et=et,
        )

    return df.apply(_one_row, axis=1)


def aggregate_timing_categories(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """
    Returns (summary_df, had_any_rows).
    summary_df columns: category_key, Category, Description, Count, Total PnL, Total PnL %.
    Always 7 rows in TIMING_CATEGORY_ORDER.
    """
    et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    prep = prepare_completed_trades_for_timing(df)
    if prep.empty:
        rows = []
        for key in TIMING_CATEGORY_ORDER:
            rows.append(
                {
                    "category_key": key,
                    "Category": TIMING_CATEGORY_LABELS[key],
                    "Description": TIMING_CATEGORY_DESCRIPTIONS[key],
                    "Count": 0,
                    "Total PnL": 0.0,
                    "Total PnL %": None,
                }
            )
        return pd.DataFrame(rows), False

    cats = classify_timing_category_dataframe(prep, et=et)
    prep = prep.copy()
    prep["_timing_cat"] = cats
    gain = pd.to_numeric(prep[COL_GAIN], errors="coerce")
    inv = pd.to_numeric(prep[COL_INVESTED], errors="coerce") if COL_INVESTED in prep.columns else pd.Series(np.nan, index=prep.index)

    rows_out = []
    for key in TIMING_CATEGORY_ORDER:
        sub = prep[prep["_timing_cat"] == key]
        cnt = int(len(sub))
        pnl_sum = float(gain.loc[sub.index].sum()) if cnt else 0.0
        inv_sum = float(inv.loc[sub.index].sum()) if cnt and inv.notna().any() else 0.0
        pct = (pnl_sum / inv_sum) if inv_sum > 0 and np.isfinite(inv_sum) else None
        rows_out.append(
            {
                "category_key": key,
                "Category": TIMING_CATEGORY_LABELS[key],
                "Description": TIMING_CATEGORY_DESCRIPTIONS[key],
                "Count": cnt,
                "Total PnL": pnl_sum,
                "Total PnL %": pct,
            }
        )
    return pd.DataFrame(rows_out), True
