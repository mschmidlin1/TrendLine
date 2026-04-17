from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from alpaca.common.exceptions import APIError
from zoneinfo import ZoneInfo

from src.configs import DISPLAY_TIMEZONE_NAME
from src.front_end.charts.net_trades_by_sell_day import colors_for_net_counts
from src.trader import StockTrader

DAILY_PCT_VTI_CHART_SESSION_KEY = "daily_pct_vs_vti_chart_prepared"

# Opacity for VTI bars only (Trendline stays solid). Tune here if the chart needs adjustment.
VTI_BAR_MARKER_ALPHA = 0.30

# Legend-only marker colors (neutral; per-bar red/green mean up/down, not series identity).
_LEGEND_GROUP_TRENDLINE = "daily_pct_trendline"
_LEGEND_GROUP_VTI = "daily_pct_vti"
_LEGEND_MARKER_TRENDLINE = "#3949ab"
_LEGEND_MARKER_VTI = "#78909c"


def colors_for_pct(vals: Sequence[float]) -> list[str]:
    """Map each blended return to green / red / gray (near-zero counts as gray)."""
    scores: list[int] = []
    for v in vals:
        if not math.isfinite(v) or math.isclose(v, 0.0, abs_tol=1e-12):
            scores.append(0)
        elif v > 0:
            scores.append(1)
        else:
            scores.append(-1)
    return colors_for_net_counts(scores)


def _trendline_blended_pct_per_day(
    full_df: pd.DataFrame,
    business_days: pd.DatetimeIndex,
    et: ZoneInfo,
) -> list[float] | None:
    if full_df.empty:
        return [0.0] * len(business_days)
    if (
        "Sold Date (ET)" not in full_df.columns
        or "Total Gain" not in full_df.columns
        or "invested" not in full_df.columns
    ):
        return None

    sell_raw = pd.to_datetime(full_df["Sold Date (ET)"], errors="coerce", utc=True)
    valid_sell = sell_raw.notna()
    sell_day = sell_raw.dt.tz_convert(et).dt.normalize()

    gain = pd.to_numeric(full_df["Total Gain"], errors="coerce")
    invested = pd.to_numeric(full_df["invested"], errors="coerce")
    ok = valid_sell & (invested > 0) & gain.notna() & invested.notna()
    work = pd.DataFrame({"sell_day": sell_day, "gain": gain, "inv": invested}).loc[ok]

    if work.empty:
        by_pct = pd.Series(dtype=float)
    else:
        grouped = work.groupby("sell_day", sort=False).agg(gain_sum=("gain", "sum"), inv_sum=("inv", "sum"))
        by_pct = grouped["gain_sum"] / grouped["inv_sum"]

    out: list[float] = []
    for d in business_days:
        v = by_pct.get(d)
        if v is None or not math.isfinite(float(v)):
            out.append(0.0)
        else:
            out.append(float(v))
    return out


def _day_to_close_from_bars(bars_df: pd.DataFrame, et: ZoneInfo) -> dict[pd.Timestamp, float]:
    if bars_df is None or bars_df.empty or "close" not in bars_df.columns:
        return {}
    d = bars_df.reset_index()
    if "timestamp" in d.columns:
        d = d.sort_values("timestamp", kind="mergesort")
        ts = pd.to_datetime(d["timestamp"], errors="coerce", utc=True)
    else:
        d = d.sort_index(kind="mergesort")
        ts = pd.to_datetime(d.index, errors="coerce", utc=True)

    ts_et = ts.dt.tz_convert(et).dt.normalize()
    day_to_close: dict[pd.Timestamp, float] = {}
    for day, close in zip(ts_et, pd.to_numeric(d["close"], errors="coerce")):
        if pd.isna(day) or pd.isna(close):
            continue
        fv = float(close)
        if not math.isfinite(fv):
            continue
        day_to_close[pd.Timestamp(day)] = fv
    return day_to_close


def _vti_pct_per_day(
    business_days: pd.DatetimeIndex,
    et: ZoneInfo,
) -> tuple[list[float | None], bool]:
    """Close-to-previous-close return per calendar day in ``business_days`` (None if no bar or no prior close)."""
    if len(business_days) == 0:
        return [], False

    first = business_days.min()
    last = business_days.max()
    start_pad = first - pd.Timedelta(days=14)
    end_pad = last + pd.Timedelta(days=1)
    start_dt: datetime = start_pad.to_pydatetime()
    end_dt: datetime = end_pad.to_pydatetime()

    try:
        bars = StockTrader().get_bars("VTI", start_dt, end_dt, "day")
    except APIError:
        return [None] * len(business_days), True

    day_to_close = _day_to_close_from_bars(bars, et)
    if not day_to_close:
        return [None] * len(business_days), True

    sorted_days = sorted(day_to_close.keys())
    out: list[float | None] = []
    for d in business_days:
        d_norm = pd.Timestamp(d)
        close_d = day_to_close.get(d_norm)
        if close_d is None:
            out.append(None)
            continue
        i = bisect.bisect_left(sorted_days, d_norm) - 1
        if i < 0:
            out.append(None)
            continue
        prev_d = sorted_days[i]
        if prev_d >= d_norm:
            out.append(None)
            continue
        prev_c = day_to_close[prev_d]
        if not math.isfinite(prev_c) or not math.isfinite(close_d) or math.isclose(prev_c, 0.0, abs_tol=1e-12):
            out.append(None)
            continue
        out.append((close_d - prev_c) / prev_c)
    return out, False


@dataclass(frozen=True)
class DailyPctVsVtiPrepared:
    """Payload for the daily % vs VTI grouped bar chart."""

    x_labels: list[str]
    trend_pct: list[float]
    vti_pct: list[float | None]
    trend_colors: list[str]
    vti_colors: list[str]
    vti_fetch_failed: bool


def _compute_daily_pct_vs_vti(full_df: pd.DataFrame) -> DailyPctVsVtiPrepared | None:
    et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    end_day = pd.Timestamp.now(tz=et).normalize()
    business_days = pd.bdate_range(end=end_day, periods=7, freq="B", tz=et)

    trend_pct = _trendline_blended_pct_per_day(full_df, business_days, et)
    if trend_pct is None:
        return None

    vti_pct, vti_failed = _vti_pct_per_day(business_days, et)
    x_labels = [bd.strftime("%a %m/%d") for bd in business_days]

    trend_colors = colors_for_pct(trend_pct)
    vti_colors = colors_for_pct([v if v is not None else 0.0 for v in vti_pct])

    return DailyPctVsVtiPrepared(
        x_labels=x_labels,
        trend_pct=trend_pct,
        vti_pct=vti_pct,
        trend_colors=trend_colors,
        vti_colors=vti_colors,
        vti_fetch_failed=vti_failed,
    )


def prepare_daily_pct_vs_vti(full_df: pd.DataFrame) -> DailyPctVsVtiPrepared | None:
    if DAILY_PCT_VTI_CHART_SESSION_KEY not in st.session_state:
        st.session_state[DAILY_PCT_VTI_CHART_SESSION_KEY] = _compute_daily_pct_vs_vti(full_df)
    return st.session_state[DAILY_PCT_VTI_CHART_SESSION_KEY]


def _daily_pct_vs_vti_figure(prepared: DailyPctVsVtiPrepared) -> go.Figure:
    trend_text = [f"{v:.2%}" for v in prepared.trend_pct]
    vti_text = [f"{v:.2%}" if v is not None else "" for v in prepared.vti_pct]

    fig = go.Figure(
        data=[
            go.Bar(
                x=prepared.x_labels,
                y=prepared.trend_pct,
                marker_color=prepared.trend_colors,
                text=trend_text,
                textposition="auto",
                legendgroup=_LEGEND_GROUP_TRENDLINE,
                showlegend=False,
            ),
            go.Bar(
                x=prepared.x_labels,
                y=prepared.vti_pct,
                marker_color=prepared.vti_colors,
                marker_opacity=VTI_BAR_MARKER_ALPHA,
                text=vti_text,
                textposition="auto",
                legendgroup=_LEGEND_GROUP_VTI,
                showlegend=False,
            ),
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=12, color=_LEGEND_MARKER_TRENDLINE, symbol="square"),
                name="Trendline",
                legendgroup=_LEGEND_GROUP_TRENDLINE,
                showlegend=True,
                hoverinfo="skip",
            ),
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    size=12,
                    color=_LEGEND_MARKER_VTI,
                    symbol="square",
                    opacity=VTI_BAR_MARKER_ALPHA,
                ),
                name="VTI",
                legendgroup=_LEGEND_GROUP_VTI,
                showlegend=True,
                hoverinfo="skip",
            ),
        ]
    )
    fig.update_layout(
        title=dict(
            text="Daily % gain by sell day vs VTI (last 7 business days, all trades)",
            x=0.5,
            xanchor="center",
        ),
        barmode="group",
        height=360,
        margin=dict(l=10, r=10, t=60, b=10),
        yaxis_title="Return",
        yaxis_tickformat=".2%",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(zeroline=True, zerolinewidth=1, zerolinecolor="#888888")
    return fig


def render_daily_pct_vs_vti_chart(full_df: pd.DataFrame) -> None:
    prepared = prepare_daily_pct_vs_vti(full_df)
    if prepared is None:
        st.info("Daily % vs VTI chart is not available.")
        return
    if prepared.vti_fetch_failed:
        st.warning("VTI benchmark data could not be loaded from Alpaca.")
    fig = _daily_pct_vs_vti_figure(prepared)
    st.plotly_chart(fig, use_container_width=True)
