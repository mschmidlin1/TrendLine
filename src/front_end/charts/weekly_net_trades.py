from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from zoneinfo import ZoneInfo

from src.configs import DISPLAY_TIMEZONE_NAME
from src.front_end.charts.net_trades_by_sell_day import (
    colors_for_net_counts,
    net_scores_per_day,
    sell_day_scores_dataframe,
)

_KEY_WEEKLY_NET_PREPARED = "weekly_net_trades_chart_prepared"


@dataclass(frozen=True)
class WeeklyNetTradesPrepared:
    """Cached bar-chart payload for the weekly net-trades chart.

    Attributes:
        x_labels: Categorical x-axis labels (weekday + date) for each business day bar.
        y_vals: Net score per day (+1 / -1 per counted trade, summed).
        colors: Bar fill colors aligned with ``y_vals`` (win / loss / flat).
    """

    x_labels: list[str]
    y_vals: list[int]
    colors: list[str]


def _compute_weekly_net_prepared(full_df: pd.DataFrame) -> WeeklyNetTradesPrepared | None:
    """Aggregate net ±1 scores for the last seven business days (display timezone).

    Arguments:
        full_df: Full news trades table (unfiltered), including sell dates and gains.

    Returns:
        Prepared bar data, or ``None`` if scoring inputs are unavailable.
    """
    et = ZoneInfo(DISPLAY_TIMEZONE_NAME)
    scored = sell_day_scores_dataframe(full_df, et)
    if scored is None:
        return None

    end_day = pd.Timestamp.now(tz=et).normalize()
    business_days = pd.bdate_range(end=end_day, periods=7, freq="B", tz=et)

    y_vals = net_scores_per_day(scored, business_days)
    x_labels = [bd.strftime("%a %m/%d") for bd in business_days]
    colors = colors_for_net_counts(y_vals)

    return WeeklyNetTradesPrepared(x_labels=x_labels, y_vals=y_vals, colors=colors)


def prepare_weekly_net_trades(full_df: pd.DataFrame) -> WeeklyNetTradesPrepared | None:
    """Return session-cached weekly net-trades data, computing it once per Streamlit session.

    Arguments:
        full_df: Full news trades table passed to the chart renderer.

    Returns:
        Cached :class:`WeeklyNetTradesPrepared`, or ``None`` if the chart cannot be built.
    """
    if _KEY_WEEKLY_NET_PREPARED not in st.session_state:
        st.session_state[_KEY_WEEKLY_NET_PREPARED] = _compute_weekly_net_prepared(full_df)
    return st.session_state[_KEY_WEEKLY_NET_PREPARED]


def _last_seven_business_days_net_bar_figure(prepared: WeeklyNetTradesPrepared) -> go.Figure:
    """Build the Plotly bar figure for last-seven-business-days net trade counts.

    Arguments:
        prepared: Categorical x labels, y values, and bar colors from :func:`prepare_weekly_net_trades`.

    Returns:
        Configured :class:`plotly.graph_objects.Figure` (not yet shown in Streamlit).
    """
    fig = go.Figure(
        data=[
            go.Bar(
                x=prepared.x_labels,
                y=prepared.y_vals,
                marker_color=prepared.colors,
                text=prepared.y_vals,
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


def render_weekly_net_trades_chart(full_df: pd.DataFrame) -> None:
    """Render the weekly net win/loss bar chart in the active Streamlit container.

    Arguments:
        full_df: Full news trades table (same source as the unfiltered snapshot).
    """
    prepared = prepare_weekly_net_trades(full_df)
    if prepared is None:
        st.info("Weekly net win/loss chart is not available.")
        return
    fig = _last_seven_business_days_net_bar_figure(prepared)
    st.plotly_chart(fig, use_container_width=True)
