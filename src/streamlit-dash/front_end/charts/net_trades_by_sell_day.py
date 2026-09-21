from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

_COLOR_GREEN = "#2ca02c"
_COLOR_RED = "#d62728"
_COLOR_GRAY = "#9e9e9e"


def sell_day_scores_dataframe(full_df: pd.DataFrame, et: ZoneInfo) -> pd.DataFrame | None:
    """Build per-row win/loss scores keyed by normalized sell calendar day in ``et``.

    Arguments:
        full_df: Trade snapshot rows; must include ``Sold Date (ET)`` and ``Total Gain``.
        et: Time zone used to convert sell timestamps and normalize to midnight dates.

    Returns:
        DataFrame with ``sell_day`` and ``score`` (1 / -1 / 0), or ``None`` if the
        frame is empty or required columns are missing.
    """
    if full_df.empty:
        return None
    if "Sold Date (ET)" not in full_df.columns or "Total Gain" not in full_df.columns:
        return None

    sell_raw = pd.to_datetime(full_df["Sold Date (ET)"], errors="coerce", utc=True)
    valid_sell = sell_raw.notna()
    sell_day = sell_raw.dt.tz_convert(et).dt.normalize()

    gain = pd.to_numeric(full_df["Total Gain"], errors="coerce")
    score = np.where(gain > 0, 1, np.where(gain < 0, -1, 0))
    scored = pd.DataFrame({"sell_day": sell_day, "score": score})
    return scored.loc[valid_sell]


def net_scores_per_day(scored: pd.DataFrame, days: pd.DatetimeIndex) -> list[int]:
    """Sum scores per calendar day for the given ordered business-day index.

    Arguments:
        scored: Output of :func:`sell_day_scores_dataframe` (``sell_day``, ``score``).
        days: Business (or other) dates to aggregate; order is preserved in the result.

    Returns:
        Net score per ``days`` entry (missing days count as 0).
    """
    if scored.empty or len(days) == 0:
        return [0] * len(days)
    by_day = scored.groupby("sell_day", sort=False)["score"].sum()
    aligned = by_day.reindex(days, fill_value=0)
    return [int(v) for v in aligned]


def colors_for_net_counts(y_vals: Sequence[int]) -> list[str]:
    """Map each net count to a bar color (green positive, red negative, gray zero).

    Arguments:
        y_vals: Net win/loss counts (typically one integer per bar / sell day).

    Returns:
        Hex color strings aligned with ``y_vals``.
    """
    out: list[str] = []
    for v in y_vals:
        if v > 0:
            out.append(_COLOR_GREEN)
        elif v < 0:
            out.append(_COLOR_RED)
        else:
            out.append(_COLOR_GRAY)
    return out
