from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.front_end.charts.net_trades_by_sell_day import colors_for_net_counts
from src.front_end.charts.timing_category import (
    TIMING_CATEGORY_LABELS,
    TIMING_CATEGORY_ORDER,
    aggregate_timing_categories,
)


def _pct_values_for_chart(summary: pd.DataFrame) -> list[float]:
    out: list[float] = []
    for k in TIMING_CATEGORY_ORDER:
        v = summary.loc[summary["category_key"] == k, "Total PnL %"].iloc[0]
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            out.append(0.0)
        else:
            out.append(float(v))
    return out


def _bar_colors_for_pct(pcts: list[float]) -> list[str]:
    scores: list[int] = []
    for p in pcts:
        if not math.isfinite(p) or math.isclose(p, 0.0, abs_tol=1e-12):
            scores.append(0)
        elif p > 0:
            scores.append(1)
        else:
            scores.append(-1)
    return colors_for_net_counts(scores)


def _timing_pnl_bar_figure(summary: pd.DataFrame) -> go.Figure:
    labels = [TIMING_CATEGORY_LABELS[k] for k in TIMING_CATEGORY_ORDER]
    pcts = _pct_values_for_chart(summary)
    counts = [int(summary.loc[summary["category_key"] == k, "Count"].iloc[0]) for k in TIMING_CATEGORY_ORDER]
    pnl_usd = [float(summary.loc[summary["category_key"] == k, "Total PnL"].iloc[0]) for k in TIMING_CATEGORY_ORDER]
    colors = _bar_colors_for_pct(pcts)
    customdata = list(zip(counts, pnl_usd))
    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=pcts,
                marker_color=colors,
                customdata=customdata,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Blended PnL %: %{y:.2%}<br>"
                    "Total PnL: $%{customdata[1]:,.2f}<br>"
                    "Count: %{customdata[0]}<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        title=dict(
            text="Blended PnL % by timing category (completed trades, valid PnL)",
            x=0.5,
            xanchor="center",
        ),
        height=420,
        margin=dict(l=10, r=10, t=60, b=120),
        yaxis_title="Total PnL ÷ invested (blended %)",
        yaxis_tickformat=".1%",
        xaxis_tickangle=-35,
        template="plotly_white",
        showlegend=False,
    )
    return fig


def render_timing_category_pnl_chart(df: pd.DataFrame) -> None:
    summary, had_rows = aggregate_timing_categories(df)
    display_tbl = summary.drop(columns=["category_key"], errors="ignore").copy()
    pct_fmt = []
    for _, r in display_tbl.iterrows():
        v = r.get("Total PnL %")
        if v is None or (isinstance(v, float) and (not math.isfinite(v))):
            pct_fmt.append("—")
        else:
            pct_fmt.append(f"{float(v):.2%}")
    display_tbl["Total PnL %"] = pct_fmt
    display_tbl["Total PnL"] = display_tbl["Total PnL"].map(lambda x: f"${float(x):,.2f}")
    col_order = ["Category", "Description", "Count", "Total PnL", "Total PnL %"]
    display_tbl = display_tbl[col_order]

    if not had_rows:
        st.info("No completed trades with valid PnL match the current filters.")
    fig = _timing_pnl_bar_figure(summary)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(display_tbl, hide_index=True, use_container_width=True)
