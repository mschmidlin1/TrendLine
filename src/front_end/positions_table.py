from __future__ import annotations

from typing import Any, List

import pandas as pd
import streamlit as st

from alpaca.trading.models import Position
from src.account_service import AccountService
from src.converters import positions_to_dataframe
from src.ticker_service import TickerService

ticker_service = TickerService()

DISPLAY_COLUMNS: List[str] = [
    "symbol",
    "qty",
    "market_value",
    "unrealized_pl",
    "unrealized_plpc",
    "avg_entry_price",
    "current_price",
]

_PREFERRED_COLUMN_ORDER = [
    "Symbol",
    "Name",
    "Shares",
    "Equity",
    "Average cost",
    "Price",
    "Total return",
    "Total return %",
]


def _company_name(symbol: str) -> str:
    try:
        return ticker_service.lookup_stock_name(symbol)
    except KeyError:
        return str(symbol)


def _positions_column_config(df: pd.DataFrame) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if "Equity" in df.columns:
        cfg["Equity"] = st.column_config.NumberColumn("Equity", format="dollar", step=0.01)
    if "Total return" in df.columns:
        cfg["Total return"] = st.column_config.NumberColumn(
            "Total return", format="dollar", step=0.01
        )
    if "Price" in df.columns:
        cfg["Price"] = st.column_config.NumberColumn("Price", format="dollar", step=0.01)
    if "Average cost" in df.columns:
        cfg["Average cost"] = st.column_config.NumberColumn(
            "Average cost", format="dollar", step=0.01
        )
    if "Shares" in df.columns:
        cfg["Shares"] = st.column_config.NumberColumn("Shares", format="%.1f")
    if "Total return %" in df.columns:
        cfg["Total return %"] = st.column_config.NumberColumn("Total return %", format="%.2f%%")
    if "Name" in df.columns:
        cfg["Name"] = st.column_config.TextColumn("Name")
    if "Symbol" in df.columns:
        cfg["Symbol"] = st.column_config.TextColumn("Symbol")
    return cfg


def render_positions_table() -> None:
    st.subheader("Current positions")
    if "positions_df" not in st.session_state:
        with st.spinner("Getting positions data...", show_time=True):
            service = AccountService()
            positions: List[Position] = service.get_all_positions()
            df = positions_to_dataframe(positions)

            if df.empty:
                st.session_state["positions_df"] = df
                st.session_state["positions_column_config"] = {}
            else:
                cols = [c for c in DISPLAY_COLUMNS if c in df.columns]
                df_display = df[cols] if cols else df.copy()
                df_display = df_display.rename(
                    columns={
                        "symbol": "Symbol",
                        "unrealized_pl": "Total return",
                        "market_value": "Equity",
                        "unrealized_plpc": "Total return %",
                        "current_price": "Price",
                        "qty": "Shares",
                        "avg_entry_price": "Average cost",
                    }
                )

                if "Symbol" in df_display.columns:
                    df_display["Name"] = df_display["Symbol"].map(_company_name)

                # Alpaca unrealized_plpc is a ratio (0.05 = 5%). Omit * 100 if values are already whole percents.
                if "Total return %" in df_display.columns:
                    df_display["Total return %"] = (
                        pd.to_numeric(df_display["Total return %"], errors="coerce") * 100
                    )

                ordered = [c for c in _PREFERRED_COLUMN_ORDER if c in df_display.columns]
                rest = [c for c in df_display.columns if c not in ordered]
                df_display = df_display[ordered + rest]

                st.session_state["positions_df"] = df_display
                st.session_state["positions_column_config"] = _positions_column_config(df_display)

    positions_df = st.session_state["positions_df"]
    if positions_df.empty:
        st.info("No open positions.")
        return

    column_config = st.session_state.get("positions_column_config") or {}
    st.dataframe(
        positions_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
    )
