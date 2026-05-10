from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_COLOR_POS = "#2ca02c"
_COLOR_NEG = "#d62728"
_COLOR_FLAT = "#7f7f7f"


@dataclass(frozen=True)
class GainPctByNewsSourcePrepared:
    x_labels: list[str]
    y_vals: list[float]
    colors: list[str]
    text_labels: list[str]


def prepare_gain_pct_by_news_source(
    df: pd.DataFrame,
) -> Literal["empty"] | Literal["no_finite"] | GainPctByNewsSourcePrepared:
    if df.empty:
        return "empty"
    if "source_name" not in df.columns:
        return "no_finite"
    if "Total Gain" not in df.columns or "invested" not in df.columns:
        return "no_finite"

    work = df.loc[df["source_name"].notna(), ["source_name", "Total Gain", "invested"]].copy()
    work["source_name"] = work["source_name"].astype(str).str.strip()
    work = work[work["source_name"] != ""]
    work["usd"] = pd.to_numeric(work["Total Gain"], errors="coerce")
    work["inv"] = pd.to_numeric(work["invested"], errors="coerce")
    work = work[
        (work["inv"] > 0)
        & np.isfinite(work["inv"].to_numpy())
        & np.isfinite(work["usd"].to_numpy())
    ]

    if work.empty:
        return "no_finite"

    # Dollar-weighted return: sum(PnL) / sum(invested). Aligns bar height with total $ vs simple mean of per-trade %.
    grouped = work.groupby("source_name", sort=False).agg(
        usd=("usd", "sum"),
        inv=("inv", "sum"),
    )
    w_pct = grouped["usd"] / grouped["inv"]
    grouped = grouped.assign(w_pct=w_pct)
    grouped = grouped[np.isfinite(grouped["w_pct"].to_numpy())]
    if grouped.empty:
        return "no_finite"

    grouped = grouped.sort_values("w_pct", ascending=False)

    x_labels = list(grouped.index.astype(str))
    y_vals = [float(v) for v in grouped["w_pct"].values]
    usd_vals = [float(v) for v in grouped["usd"].values]
    inv_vals = [float(v) for v in grouped["inv"].values]
    colors = [
        _COLOR_POS if y > 0 else _COLOR_NEG if y < 0 else _COLOR_FLAT
        for y in y_vals
    ]

    def _money(u: float) -> str:
        if not math.isfinite(u):
            return "—"
        return f"${u:,.2f}"

    # Show sum invested so % vs $ is auditable (high % on small capital can beat low % on large $ in dollars).
    text_labels = [
        f"{w:.2%}<br>{_money(usd)} PnL<br>{_money(inv)} invested"
        for w, usd, inv in zip(y_vals, usd_vals, inv_vals, strict=True)
    ]
    return GainPctByNewsSourcePrepared(
        x_labels=x_labels,
        y_vals=y_vals,
        colors=colors,
        text_labels=text_labels,
    )


def _gain_pct_by_source_bar_figure(prepared: GainPctByNewsSourcePrepared) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Bar(
                x=prepared.x_labels,
                y=prepared.y_vals,
                marker_color=prepared.colors,
                text=prepared.text_labels,
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title=dict(
            text=(
                "Return on capital by news source (current filters)"
                "<br><sup>Bar = total PnL / total invested (weighted %). Labels: that %, total PnL, and capital deployed</sup>"
            ),
            x=0.5,
            xanchor="center",
        ),
        height=360,
        margin=dict(l=10, r=10, t=60, b=10),
        yaxis_title="Total PnL / total invested (per source)",
        template="plotly_white",
        showlegend=False,
    )
    fig.update_xaxes(tickangle=-35)
    fig.update_yaxes(
        tickformat=".0%",
        zeroline=True,
        zerolinewidth=1,
        zerolinecolor="#888888",
    )
    return fig


def render_gain_pct_by_news_source_chart(df: pd.DataFrame) -> None:
    prepared = prepare_gain_pct_by_news_source(df)
    if prepared == "empty":
        st.info("No rows match the current filters.")
        return
    if prepared == "no_finite":
        st.info(
            "No trades with a news source, positive invested amount, and finite PnL in the current filter."
        )
        return
    fig = _gain_pct_by_source_bar_figure(prepared)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Bar height is return on capital, not total profit. A higher % can still be fewer dollars "
        "if that source had much less capital deployed (PnL divided by invested on each bar matches the %)."
    )
