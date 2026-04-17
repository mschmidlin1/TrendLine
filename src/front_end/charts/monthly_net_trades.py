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

_KEY_MONTHLY_NET_PREPARED = "monthly_net_trades_chart_prepared"


@dataclass(frozen=True)
class MonthlyNetTradesPrepared:
    """Cached bar-chart payload for the monthly net-trades chart (datetime x-axis).

    Attributes:
        x_dates: Timezone-aware midnight timestamps for each business-day bar.
        y_vals: Net score per day (+1 / -1 per counted trade, summed).
        colors: Bar fill colors aligned with ``y_vals`` (win / loss / flat).
    """

    x_dates: list[pd.Timestamp]
    y_vals: list[int]
    colors: list[str]


def _compute_monthly_net_prepared(full_df: pd.DataFrame) -> MonthlyNetTradesPrepared | None:
    """Aggregate net ±1 scores for business days in the last ~one calendar month (ET).

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
    start_day = (end_day - pd.DateOffset(months=1)).normalize()
    business_days = pd.bdate_range(start=start_day, end=end_day, freq="B", tz=et)

    y_vals = net_scores_per_day(scored, business_days)
    x_dates = [pd.Timestamp(bd) for bd in business_days]
    colors = colors_for_net_counts(y_vals)

    return MonthlyNetTradesPrepared(x_dates=x_dates, y_vals=y_vals, colors=colors)


def prepare_monthly_net_trades(full_df: pd.DataFrame) -> MonthlyNetTradesPrepared | None:
    """Return session-cached monthly net-trades data, computing it once per Streamlit session.

    Arguments:
        full_df: Full news trades table passed to the chart renderer.

    Returns:
        Cached :class:`MonthlyNetTradesPrepared`, or ``None`` if the chart cannot be built.
    """
    if _KEY_MONTHLY_NET_PREPARED not in st.session_state:
        st.session_state[_KEY_MONTHLY_NET_PREPARED] = _compute_monthly_net_prepared(full_df)
    return st.session_state[_KEY_MONTHLY_NET_PREPARED]


def _monthly_net_bar_figure(prepared: MonthlyNetTradesPrepared) -> go.Figure:
    """Build the Plotly bar figure for monthly net trade counts (date axis, sparse ticks).

    Arguments:
        prepared: Datetime x values, y values, and bar colors from :func:`prepare_monthly_net_trades`.

    Returns:
        Configured :class:`plotly.graph_objects.Figure` (not yet shown in Streamlit).
    """
    fig = go.Figure(
        data=[
            go.Bar(
                x=prepared.x_dates,
                y=prepared.y_vals,
                marker_color=prepared.colors,
                text=prepared.y_vals,
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title=dict(
            text="Net win/loss trades by sell day (last ~1 month of business days, all trades)",
            x=0.5,
            xanchor="center",
        ),
        height=360,
        margin=dict(l=10, r=10, t=60, b=10),
        yaxis_title="Net (+1 / -1 per trade)",
        template="plotly_white",
        showlegend=False,
    )
    fig.update_xaxes(
        type="date",
        tickformat="%b %d",
        tickangle=-45,
        nticks=8,
    )
    fig.update_yaxes(zeroline=True, zerolinewidth=1, zerolinecolor="#888888")
    return fig


def render_monthly_net_trades_chart(full_df: pd.DataFrame) -> None:
    """Render the monthly net win/loss bar chart in the active Streamlit container.

    Arguments:
        full_df: Full news trades table (same source as the unfiltered snapshot).
    """
    prepared = prepare_monthly_net_trades(full_df)
    if prepared is None:
        st.info("Monthly net win/loss chart is not available.")
        return
    fig = _monthly_net_bar_figure(prepared)
    st.plotly_chart(fig, use_container_width=True)
