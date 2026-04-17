from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
from alpaca.common.exceptions import APIError

from src.front_end.charts import (
    render_daily_pct_vs_vti_chart,
    render_monthly_net_trades_chart,
    render_sentiment_outcome_chart,
    render_weekly_net_trades_chart,
)
from src.front_end.charts.daily_pct_vs_vti import DAILY_PCT_VTI_CHART_SESSION_KEY
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
    ("VTI", "Vanguard Total Stock Market (VTI)"),
)

_KEY_SENTIMENT = "news_filter_sentiment"
_KEY_TIME_PRESET = "news_filter_time_preset"
_KEY_BENCHMARK_BY_PRESET = "news_benchmark_by_preset"
_KEY_EXCLUDE_NONE_GAIN = "news_filter_exclude_none_gain"
_KEY_HEADLINE = "news_filter_headline"
_KEY_COMPANY = "news_filter_company"
_KEY_APPLY = "news_filter_apply"


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


def _benchmark_time_bounds(preset: str, news_df: pd.DataFrame, et: ZoneInfo) -> tuple[pd.Timestamp, pd.Timestamp] | None:
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
    first = float(d["open"].iloc[0])
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

    st.session_state[_KEY_EXCLUDE_NONE_GAIN] = False

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

    if st.session_state.get(_KEY_EXCLUDE_NONE_GAIN):
        gain = pd.to_numeric(df["Total Gain"], errors="coerce")
        arr = gain.to_numpy(dtype=float, copy=True)
        df = df[np.isfinite(arr)]

    headline_q = (st.session_state.get(_KEY_HEADLINE) or "").strip()
    if headline_q:
        df = df[df["Headline"].astype(str).str.contains(headline_q, case=False, na=False)]

    company_q = (st.session_state.get(_KEY_COMPANY) or "").strip()
    if company_q:
        df = df[df["Company"].astype(str).str.contains(company_q, case=False, na=False)]

    st.session_state["news_table_filtered"] = df


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
            st.session_state.pop(DAILY_PCT_VTI_CHART_SESSION_KEY, None)

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
        text_col1, text_col2 = st.columns(2)
        with text_col1:
            st.text_input("Search Headlines", key=_KEY_HEADLINE)
        with text_col2:
            st.text_input("Search Company", key=_KEY_COMPANY)
        st.checkbox("Only Completed Trades", key=_KEY_EXCLUDE_NONE_GAIN)
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
    with st.container():
        pos_neg_trades_tab, weekly_net_trades_tab, monthly_net_trades_tab, daily_pct_vti_tab = st.tabs(
            [
                "Pos Vs Neg Trades (Filtered)",
                "Weekly Net Trades",
                "Monthly Net Trades",
                "Daily % vs VTI",
            ]
        )
        with pos_neg_trades_tab:
            render_sentiment_outcome_chart(df)
        with weekly_net_trades_tab:
            render_weekly_net_trades_chart(st.session_state["news_table"])
        with monthly_net_trades_tab:
            render_monthly_net_trades_chart(st.session_state["news_table"])
        with daily_pct_vti_tab:
            render_daily_pct_vs_vti_chart(st.session_state["news_table"])
