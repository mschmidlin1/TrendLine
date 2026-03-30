from __future__ import annotations

import streamlit as st
from src.front_end.equity_plot import render_equity_plot
from src.front_end.positions_table import render_positions_table
from src.front_end.trades_table import render_trades_table
from src.front_end.log_viewer import render_log_viewer
import base64
from pathlib import Path

def main() -> None:
    st.set_page_config(page_title="TrendLine Dashboard", layout="wide")
    st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2.7rem;
            padding-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)
    path = Path("resources/logo_small.png")
    b64 = base64.b64encode(path.read_bytes()).decode()
    mime = "image/png"  # use "image/jpeg" for .jpg
    st.markdown(
    f"""
    <div style="
        position: relative;
        width: 100%;
        min-height: 180px;
        margin-bottom: 0.1rem;
    ">
        <div style="
            position: absolute;
            top: 0;
            left: 0;
            width: 180px;
            height: 180px;
            border-radius: 50%;
            overflow: hidden;
        ">
            <img
                src="data:{mime};base64,{b64}"
                alt="Logo"
                style="
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                    object-position: center center;
                    transform: scale(1.35);
                    transform-origin: center center;
                "
            />
        </div>
        <div style="
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            text-align: right;
        ">
            <h1 style="
                margin: 0;
                font-size: clamp(2.5rem, 6vw, 4.5rem);
                font-weight: 700;
                line-height: 1.05;
            ">Dashboard</h1>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
    # left, right = st.columns([1, 1])
    # with left:
    #     #st.image("resources/logo_big.png", width=600)

    #     st.markdown(
    #         f"""
    #         <div style="text-align: left;">
    #         <div style="
    #             width: 240px;
    #             height: 240px;
    #             border-radius: 50%;
    #             overflow: hidden;
    #             display: inline-block;
    #         ">
    #             <img
    #             src="data:{mime};base64,{b64}"
    #             alt="Logo"
    #             style="
    #                 width: 100%;
    #                 height: 100%;
    #                 object-fit: cover;
    #                 object-position: center center;
    #                 transform: scale(1.35);
    #                 transform-origin: center center;
    #             "
    #             />
    #         </div>
    #         </div>
    #         """,
    #         unsafe_allow_html=True,
    #     )
    # with right:
    #     st.title("TrendLine Dashboard")
    st.divider()
    render_equity_plot()
    st.divider()
    render_positions_table()
    st.divider()
    render_trades_table()
    st.divider()
    render_log_viewer()
    # tab_equity, tab_trades, tab_logs = st.tabs(["Equity", "Archived Trades", "Logs"])

    # with tab_equity:
    #     try:
    #         render_equity_plot()
    #     except Exception as e:
    #         st.error("Failed to render equity history.")
    #         st.exception(e)
    #     try:
    #         render_positions_table()
    #     except Exception as e:
    #         st.error("Failed to render current positions.")
    #         st.exception(e)

    # with tab_trades:
    #     try:
    #         render_trades_table()
    #     except Exception as e:
    #         st.error("Failed to render archived trades.")
    #         st.exception(e)

    # with tab_logs:
    #     try:
    #         render_log_viewer()
    #     except Exception as e:
    #         st.error("Failed to render logs.")
    #         st.exception(e)


if __name__ == "__main__":
    main()

