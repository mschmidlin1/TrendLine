from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from alpaca.common.exceptions import APIError

from src.front_end.trade_snapshot_loader import load_trade_lifecycle_from_disk
from src.trade_lifecycle_manager import TradeLifecycleManager
from src.ticker_service import TickerService
from src.trader import StockTrader
from src.configs import DISPLAY_TIMEZONE_NAME
from src.base.datetime_utils import convert_series_to_display_tz

_NEWS_TIME_PRESET_LABELS = ["1D", "1W", "1M", "3M", "YTD", "1Y", "ALL"]

_BENCHMARK_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("SPY", "S&P 500 (SPY)"),
    ("DIA", "Dow Jones (DIA)"),
    ("QQQ", "Nasdaq-100 (QQQ)"),
)

_KEY_SENTIMENT = "news_filter_sentiment"
_KEY_TIME_PRESET = "news_filter_time_preset"
_KEY_BENCHMARK_BY_PRESET = "news_benchmark_by_preset"
_KEY_GAIN_MIN = "news_filter_gain_min"
_KEY_GAIN_MAX = "news_filter_gain_max"
_KEY_HEADLINE = "news_filter_headline"
_KEY_COMPANY = "news_filter_company"
_KEY_APPLY = "news_filter_apply"
_KEY_WEEKLY_NET_CHART = "weekly_net_trades_chart_figure"


def _compute_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    buy_qty = pd.to_numeric(df.get("buy_order_qty"), errors="coerce")
    buy_avg = pd.to_numeric(df.get("buy_order_filled_avg_price"), errors="coerce")
    sell_qty = pd.to_numeric(df.get("sell_order_qty"), errors="coerce")
    sell_avg = pd.to_numeric(df.get("sell_order_filled_avg_price"), errors="coerce")

    invested = buy_qty * buy_avg
    proceeds = sell_qty * sell_avg

    pnl = proceeds - invested
    pnl_pct = pnl / invested.replace({0: pd.NA})

    df["invested"] = invested
    df["proceeds"] = proceeds
    df["pnl"] = pnl
    df["pnl_pct"] = pnl_pct
    return df


def _news_time_preset_bounds(preset: str, et: ZoneInfo) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if preset == "ALL":
        return None
    now_et = pd.Timestamp.now(tz=et)
    if preset == "1D":
        start = now_et - pd.Timedelta(days=1)
    elif preset == "1W":
        start = now_et - pd.Timedelta(weeks=1)
    elif preset == "1M":
        start = now_et - pd.DateOffset(months=1)
    elif preset == "3M":
        start = now_et - pd.DateOffset(months=3)
    elif preset == "YTD":
        start = pd.Timestamp(year=now_et.year, month=1, day=1, tz=et)
    elif preset == "1Y":
        start = now_et - pd.DateOffset(years=1)
    else:
        start = now_et - pd.DateOffset(months=1)
    return (start, now_et)


def _benchmark_time_bounds(
    preset: str, news_df: pd.DataFrame, et: ZoneInfo
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """
    Calendar window used to fetch benchmark bars for this preset.
    ALL uses min/max Date (ET) on the full snapshot (see plan).
    """
    if preset == "ALL":
        if news_df.empty or "Date (ET)" not in news_df.columns:
            return None
        ts = pd.to_datetime(news_df["Date (ET)"], errors="coerce", utc=True)
        if not ts.notna().any():
            return None
        ts_et = ts.dt.tz_convert(et)
        start = ts_et.min()
        end = ts_et.max()
        if start > end:
            start, end = end, start
        return (start, end)
    return _news_time_preset_bounds(preset, et)


def _close_to_close_pct_from_bars(bars_df: pd.DataFrame) -> float | None:
    if bars_df is None or bars_df.empty or "close" not in bars_df.columns:
        return None
    d = bars_df.reset_index()
    if "timestamp" in d.columns:
        d = d.sort_values("timestamp", kind="mergesort")
    else:
        d = d.sort_index(kind="mergesort")
    first = float(d["close"].iloc[0])
    last = float(d["close"].iloc[-1])
    if not math.isfinite(first) or not math.isfinite(last) or math.isclose(first, 0.0, abs_tol=1e-12):
        return None
    return (last - first) / first


def _prefetch_news_benchmarks(news_df: pd.DataFrame) -> None:
    et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    trader = StockTrader()
    by_preset: dict[str, dict[str, float | None]] = {}
    any_fail = False

    for preset in _NEWS_TIME_PRESET_LABELS:
        label_to_pct: dict[str, float | None] = {lbl: None for _, lbl in _BENCHMARK_SYMBOLS}
        bounds = _benchmark_time_bounds(preset, news_df, et)
        if bounds is None:
            by_preset[preset] = label_to_pct
            continue
        start_ts, end_ts = bounds
        if start_ts > end_ts:
            start_ts, end_ts = end_ts, start_ts
        # Alpaca bar `end` is typically exclusive; extend slightly so the window includes the end day.
        start_dt: datetime = start_ts.to_pydatetime()
        end_dt: datetime = (end_ts + pd.Timedelta(days=1)).to_pydatetime()

        for sym, lbl in _BENCHMARK_SYMBOLS:
            try:
                bars = trader.get_bars(sym, start_dt, end_dt, "day")
            except APIError:
                any_fail = True
                label_to_pct[lbl] = None
                continue
            label_to_pct[lbl] = _close_to_close_pct_from_bars(bars)

        by_preset[preset] = label_to_pct

    st.session_state[_KEY_BENCHMARK_BY_PRESET] = by_preset
    if any_fail:
        st.warning("Some benchmark data could not be loaded from Alpaca.")


def _initialize_news_filter_widget_defaults() -> None:
    st.session_state[_KEY_SENTIMENT] = []

    st.session_state[_KEY_GAIN_MIN] = 0.0
    st.session_state[_KEY_GAIN_MAX] = 0.0

    st.session_state[_KEY_HEADLINE] = ""
    st.session_state[_KEY_COMPANY] = ""


def apply_news_table_filters() -> None:
    df = st.session_state["news_table"].copy()

    sentiments = st.session_state.get(_KEY_SENTIMENT) or []
    if sentiments:
        df = df[df["Sentiment"].isin(sentiments)]

    et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    ts_series = pd.to_datetime(df["Date (ET)"], errors="coerce", utc=True).dt.tz_convert(et)
    if ts_series.notna().any():
        preset = st.session_state.get(_KEY_TIME_PRESET, "1M")
        bounds = _news_time_preset_bounds(preset, et)
        if bounds is not None:
            start_ts, end_ts = bounds
            if start_ts > end_ts:
                start_ts, end_ts = end_ts, start_ts
            start_bound = start_ts.floor("s")
            end_inclusive = end_ts.floor("s") + pd.Timedelta(seconds=1) - pd.Timedelta(nanoseconds=1)
            in_range = (ts_series >= start_bound) & (ts_series <= end_inclusive)
            df = df[in_range]

    gain = pd.to_numeric(df["Total Gain"], errors="coerce")
    gmin = float(st.session_state[_KEY_GAIN_MIN])
    gmax = float(st.session_state[_KEY_GAIN_MAX])
    if gmin > gmax:
        gmin, gmax = gmax, gmin
    gain_filter_off = math.isclose(gmin, 0.0, abs_tol=1e-9) and math.isclose(gmax, 0.0, abs_tol=1e-9)
    if not gain_filter_off:
        arr = gain.to_numpy(dtype=float, copy=True)
        finite_mask = np.isfinite(arr)
        gain_mask = finite_mask & (gain >= gmin) & (gain <= gmax)
        df = df[gain_mask]

    headline_q = (st.session_state.get(_KEY_HEADLINE) or "").strip()
    if headline_q:
        df = df[df["Headline"].astype(str).str.contains(headline_q, case=False, na=False)]

    company_q = (st.session_state.get(_KEY_COMPANY) or "").strip()
    if company_q:
        df = df[df["Company"].astype(str).str.contains(company_q, case=False, na=False)]

    st.session_state["news_table_filtered"] = df


def _sentiment_outcome_bar_figure(df: pd.DataFrame) -> go.Figure | None:
    if df.empty or "Total Gain" not in df.columns:
        return None
    gain = pd.to_numeric(df["Total Gain"], errors="coerce")
    correct = int((gain > 0).sum())
    incorrect = int((gain < 0).sum())
    if correct == 0 and incorrect == 0:
        return None
    fig = go.Figure(
        data=[
            go.Bar(
                x=["Correct sentiment", "Incorrect sentiment"],
                y=[correct, incorrect],
                marker_color=["#2ca02c", "#d62728"],
                text=[correct, incorrect],
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title=dict(text="Count of Positive Vs Negative Gain Trades", x=0.5, xanchor="center"),
        height=360,
        margin=dict(l=10, r=10, t=60, b=10),
        yaxis_title="Count",
        template="plotly_white",
        showlegend=False,
    )
    return fig


def _last_seven_business_days_net_bar_figure(full_df: pd.DataFrame) -> go.Figure | None:
    if full_df.empty:
        return None
    if "Sold Date (ET)" not in full_df.columns or "Total Gain" not in full_df.columns:
        return None

    et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    sell_raw = pd.to_datetime(full_df["Sold Date (ET)"], errors="coerce", utc=True)
    valid_sell = sell_raw.notna()
    sell_day = sell_raw.dt.tz_convert(et).dt.normalize()

    gain = pd.to_numeric(full_df["Total Gain"], errors="coerce")
    score = np.where(gain > 0, 1, np.where(gain < 0, -1, 0))
    scored = pd.DataFrame({"sell_day": sell_day, "score": score})
    scored = scored.loc[valid_sell]

    end_day = pd.Timestamp.now(tz=et).normalize()
    business_days = pd.bdate_range(end=end_day, periods=7, freq="B", tz=et)

    green = "#2ca02c"
    red = "#d62728"
    gray = "#9e9e9e"
    x_labels: list[str] = []
    y_vals: list[int] = []
    colors: list[str] = []

    for bd in business_days:
        day_net = int(scored.loc[scored["sell_day"] == bd, "score"].sum())
        x_labels.append(bd.strftime("%a %m/%d"))
        y_vals.append(day_net)
        if day_net > 0:
            colors.append(green)
        elif day_net < 0:
            colors.append(red)
        else:
            colors.append(gray)

    fig = go.Figure(
        data=[
            go.Bar(
                x=x_labels,
                y=y_vals,
                marker_color=colors,
                text=y_vals,
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title=dict(
            text="Net win/loss trades by sell day (last 7 business days, all trades)",
            x=0.5,
            xanchor="center",
        ),
        height=360,
        margin=dict(l=10, r=10, t=60, b=10),
        yaxis_title="Net (+1 / -1 per trade)",
        template="plotly_white",
        showlegend=False,
    )
    fig.update_yaxes(zeroline=True, zerolinewidth=1, zerolinecolor="#888888")
    return fig


def render_trades_table() -> None:
    st.subheader("News Trades")
    if "news_table" not in st.session_state:
        with st.spinner("Getting news trade data...", show_time=True):
            manager: TradeLifecycleManager = load_trade_lifecycle_from_disk()
            if manager is None:
                st.warning("No trade snapshot found on disk yet (persistent_data/trade_lifecycle.snapshot).")
                return

            df = manager.to_dataframe()
            if df.empty:
                st.warning("Trade snapshot is present but contains no entries.")
                return

            df = _compute_derived_metrics(df)
            tz = DISPLAY_TIMEZONE_NAME
            for col in ("archived_at", "buy_order_filled_at", "sell_order_filled_at"):
                if col in df.columns:
                    df[col] = convert_series_to_display_tz(df[col], tz)
            df = df.sort_values("archived_at", ascending=False, na_position="last")

            ticker_service = TickerService()

            df["Company"] = df["ticker"].apply(ticker_service.lookup_stock_name)
            df = df.rename(columns={
                "pnl": "Total Gain",
                "pnl_pct": "Total Gain %",
                "archived_at": "Date (ET)",
                "title": "Headline",
                "ticker": "Ticker",
                "sentiment": "Sentiment",
                "buy_order_filled_at": "Purchased Date (ET)",
                "sell_order_filled_at": "Sold Date (ET)",
            })

            st.session_state["news_table"] = df
            st.session_state.pop(_KEY_BENCHMARK_BY_PRESET, None)

    if "news_table" not in st.session_state:
        return

    if _KEY_WEEKLY_NET_CHART not in st.session_state:
        st.session_state[_KEY_WEEKLY_NET_CHART] = _last_seven_business_days_net_bar_figure(
            st.session_state["news_table"],
        )

    df_ref = st.session_state["news_table"]
    st.session_state.pop("news_filter_date_start", None)
    st.session_state.pop("news_filter_date_end", None)
    if "news_table_filtered" not in st.session_state:
        st.session_state["news_table_filtered"] = df_ref.copy()
    if _KEY_SENTIMENT not in st.session_state:
        _initialize_news_filter_widget_defaults()
        apply_news_table_filters()

    if _KEY_BENCHMARK_BY_PRESET not in st.session_state:
        with st.spinner("Loading benchmark data...", show_time=True):
            _prefetch_news_benchmarks(st.session_state["news_table"])

    col_order = [
        "Date (ET)", "Headline", "Ticker", "Company", "Sentiment",
        "Purchased Date (ET)", "Sold Date (ET)", "Total Gain", "Total Gain %",
    ]

    sentiment_opts = sorted(df_ref["Sentiment"].dropna().unique(), key=lambda x: str(x))

    with st.expander("Filter Controls"):
        st.multiselect("Sentiment", sentiment_opts, key=_KEY_SENTIMENT)
        total_gain_col1, total_gain_col2 = st.columns(2)
        with total_gain_col1:
            st.number_input("Min Gain", step=0.0001, format="%.4f", key=_KEY_GAIN_MIN)
        with total_gain_col2:
            st.number_input("Max Gain", step=0.0001, format="%.4f", key=_KEY_GAIN_MAX)
        text_col1, text_col2 = st.columns(2)
        with text_col1:
            st.text_input("Search Headlines", key=_KEY_HEADLINE)
        with text_col2:
            st.text_input("Search Company", key=_KEY_COMPANY)
        if st.button("Apply", key=_KEY_APPLY):
            apply_news_table_filters()

    st.radio(
        "Time preset",
        options=_NEWS_TIME_PRESET_LABELS,
        index=_NEWS_TIME_PRESET_LABELS.index("1M"),
        horizontal=True,
        key=_KEY_TIME_PRESET,
        on_change=apply_news_table_filters,
    )

    st.dataframe(
        st.session_state["news_table_filtered"],
        use_container_width=True,
        hide_index=True,
        column_order=col_order,
    )

    df = st.session_state["news_table_filtered"]
    total_usd = df["Total Gain"].sum()
    total_invested = df["invested"].sum()
    if pd.notna(total_invested) and total_invested > 0:
        total_pct = float(total_usd / total_invested)
    else:
        total_pct = None

    col_usd, col_pct = st.columns(2)
    with col_usd:
        usd_display = f"${total_usd:,.2f}" if pd.notna(total_usd) else "—"
        st.metric("Total gain", usd_display)
    with col_pct:
        pct_display = f"{total_pct:.2%}" if total_pct is not None and pd.notna(total_pct) else "—"
        st.metric("Total gain %", pct_display)

    preset_key = st.session_state.get(_KEY_TIME_PRESET, "1M")
    bench_by_preset = st.session_state.get(_KEY_BENCHMARK_BY_PRESET) or {}
    bench_row = bench_by_preset.get(preset_key) or {}
    bench_table_rows = []
    for _sym, bench_lbl in _BENCHMARK_SYMBOLS:
        v = bench_row.get(bench_lbl)
        try:
            fv = float(v)
            pct_str = f"{fv:.2%}" if math.isfinite(fv) else "—"
        except (TypeError, ValueError):
            pct_str = "—"
        bench_table_rows.append({"Benchmark": bench_lbl, "Change": pct_str})
    # st.table always shows a row-index column; st.dataframe can hide it.
    st.dataframe(
        pd.DataFrame(bench_table_rows),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Charts")
    fig_sentiment = _sentiment_outcome_bar_figure(df)
    if df.empty:
        st.info("No rows match the current filters.")
    elif fig_sentiment is None:
        st.info("No trades with positive or negative PnL in the current filter.")
    else:
        st.plotly_chart(fig_sentiment, use_container_width=True)

    fig_weekly = st.session_state.get(_KEY_WEEKLY_NET_CHART)
    if fig_weekly is None:
        st.info("Weekly net win/loss chart is not available.")
    else:
        st.plotly_chart(fig_weekly, use_container_width=True)
