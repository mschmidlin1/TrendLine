from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


@dataclass(frozen=True)
class _SentimentCounts:
    correct: int
    incorrect: int


def prepare_sentiment_outcome(
    df: pd.DataFrame,
) -> Literal["empty"] | Literal["no_sign"] | _SentimentCounts:
    if df.empty:
        return "empty"
    if "Total Gain" not in df.columns:
        return "no_sign"
    gain = pd.to_numeric(df["Total Gain"], errors="coerce")
    correct = int((gain > 0).sum())
    incorrect = int((gain < 0).sum())
    if correct == 0 and incorrect == 0:
        return "no_sign"
    return _SentimentCounts(correct=correct, incorrect=incorrect)


def _sentiment_outcome_bar_figure(counts: _SentimentCounts) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Bar(
                x=["Correct sentiment", "Incorrect sentiment"],
                y=[counts.correct, counts.incorrect],
                marker_color=["#2ca02c", "#d62728"],
                text=[counts.correct, counts.incorrect],
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


def render_sentiment_outcome_chart(df: pd.DataFrame) -> None:
    prepared = prepare_sentiment_outcome(df)
    if prepared == "empty":
        st.info("No rows match the current filters.")
        return
    if prepared == "no_sign":
        st.info("No trades with positive or negative PnL in the current filter.")
        return
    fig = _sentiment_outcome_bar_figure(prepared)
    st.plotly_chart(fig, use_container_width=True)
