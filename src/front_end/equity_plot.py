from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Dict, Tuple, List
from src.account_service import HistoricalDataService
from alpaca.trading.models import PortfolioHistory
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime


labels = ["1D", "1W", "1M", "3M", "YTD", "1Y", "ALL"]

def portfolio_history_to_data(ph: PortfolioHistory) -> Tuple[List[datetime], list[float]]:
    dates = []
    moneys = []
    for timestamp, equity in zip(ph.timestamp, ph.equity):
        dates.append(datetime.fromtimestamp(timestamp))
        moneys.append(equity)
    return (dates, moneys)

def _get_data():
    if "equity_data_cache" not in st.session_state:
        with st.spinner("Getting equity data...", show_time=True):
            equity_data: Dict[str, Any] = dict[str, Any]()
            service = HistoricalDataService()
            for label in labels:
                if label == "1D":
                    equity_data["1D"] = portfolio_history_to_data(service.get_history_1d())
                elif label == "1W":
                    equity_data["1W"] = portfolio_history_to_data(service.get_history_1w())
                elif label == "1M":
                    equity_data["1M"] = portfolio_history_to_data(service.get_history_1m())
                elif label == "3M":
                    equity_data["3M"] = portfolio_history_to_data(service.get_history_3m())
                elif label == "YTD":
                    equity_data["YTD"] = portfolio_history_to_data(service.get_history_ytd())
                elif label == "1Y":
                    equity_data["1Y"] = portfolio_history_to_data(service.get_history_1y())
                elif label == "ALL":
                    equity_data["ALL"] = portfolio_history_to_data(service.get_history_all())
            st.session_state["equity_data_cache"] = equity_data

def render_time_preset_buttons() -> str:
    
    return st.radio(
        "Time preset",
        options=labels,
        index=1,                 # default: "1W" based on your PRESETS order
        horizontal=True,
        key="equity_time_preset",
    ) 




def render_equity_plot() -> None:
    st.subheader("Total Equity Over Time")
    
    _get_data()

    choice = render_time_preset_buttons()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=st.session_state["equity_data_cache"][choice][0],
            y=st.session_state["equity_data_cache"][choice][1],
            mode="lines",
            name="Equity",
        )
    )

    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Time",
        yaxis_title="Equity",
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)
    
