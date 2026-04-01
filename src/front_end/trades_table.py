from __future__ import annotations

import pandas as pd
import streamlit as st

from src.front_end.trade_snapshot_loader import load_trade_lifecycle_from_disk
from src.trade_lifecycle_manager import TradeLifecycleManager
from src.ticker_service import TickerService
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

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
            df = df.sort_values("archived_at", ascending=False, na_position="last")

            # Streamlit renders datetimes reasonably; for long titles, keep the UI readable.
            # if "title" in df_display.columns:
            #     df_display = df_display.copy()
            #     df_display["title"] = df_display["title"].astype(str).str.slice(0, 120)
            
            ticker_service = TickerService()
            
            df["Company"] = df["ticker"].apply(ticker_service.lookup_stock_name)
            df = df.rename(columns={
                "pnl": "Total Gain",
                "pnl_pct": "Total Gain %",
                "archived_at": "Date",
                "title": "Headline",
                "ticker": "Ticker",
                "sentiment": "Sentiment",
                "buy_order_filled_at": "Purchased Date",
                "sell_order_filled_at": "Sold Date",
            })

            st.session_state["news_table"] = df
    
    
    col_order = ["Date", "Headline", "Ticker", "Company", "Sentiment", "Purchased Date", "Sold Date", "Total Gain", "Total Gain %"]
    #Source_name, Shares, buy order status, sell order status
    st.dataframe(st.session_state["news_table"], use_container_width=True, hide_index=True, column_order=col_order)
    #AgGrid(data=st.session_state["news_table"])

    df = st.session_state["news_table"]
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
