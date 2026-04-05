from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from src.front_end.trade_snapshot_loader import load_trade_lifecycle_from_disk
from src.trade_lifecycle_manager import TradeLifecycleManager
from src.ticker_service import TickerService
from src.configs import DISPLAY_TIMEZONE_NAME
from src.base.datetime_utils import convert_series_to_display_tz

_KEY_SENTIMENT = "news_filter_sentiment"
_KEY_DATE_START = "news_filter_date_start"
_KEY_DATE_END = "news_filter_date_end"
_KEY_GAIN_MIN = "news_filter_gain_min"
_KEY_GAIN_MAX = "news_filter_gain_max"
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


def _ui_datetime_to_et_timestamp(d: datetime) -> pd.Timestamp:
    et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    if d.tzinfo is None:
        return pd.Timestamp(d).tz_localize(et, ambiguous="NaT", nonexistent="shift_forward")
    return pd.Timestamp(d).tz_convert(et)


def _initialize_news_filter_widget_defaults() -> None:
    st.session_state[_KEY_SENTIMENT] = []

    et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    now_et = pd.Timestamp.now(tz=et)
    month_ago_et = now_et - pd.DateOffset(months=1)
    st.session_state[_KEY_DATE_START] = month_ago_et.to_pydatetime().replace(tzinfo=None)
    st.session_state[_KEY_DATE_END] = now_et.to_pydatetime().replace(tzinfo=None)

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
        start_ts = _ui_datetime_to_et_timestamp(st.session_state[_KEY_DATE_START])
        end_ts = _ui_datetime_to_et_timestamp(st.session_state[_KEY_DATE_END])
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

    if "news_table" not in st.session_state:
        return

    df_ref = st.session_state["news_table"]
    if "news_table_filtered" not in st.session_state:
        st.session_state["news_table_filtered"] = df_ref.copy()
    if _KEY_SENTIMENT not in st.session_state:
        _initialize_news_filter_widget_defaults()
        apply_news_table_filters()

    col_order = [
        "Date (ET)", "Headline", "Ticker", "Company", "Sentiment",
        "Purchased Date (ET)", "Sold Date (ET)", "Total Gain", "Total Gain %",
    ]

    sentiment_opts = sorted(df_ref["Sentiment"].dropna().unique(), key=lambda x: str(x))

    with st.expander("Filter Controls"):
        st.multiselect("Sentiment", sentiment_opts, key=_KEY_SENTIMENT)
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            st.datetime_input("Date (ET): Start", key=_KEY_DATE_START)
        with date_col2:
            st.datetime_input("Date (ET): End", key=_KEY_DATE_END)
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
