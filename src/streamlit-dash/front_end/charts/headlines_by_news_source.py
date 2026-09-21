from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PURCHASE_DATE_COL = "Purchased Date (ET)"


@dataclass(frozen=True)
class ArticleCountsBySourcePrepared:
    labels: list[str]
    values: list[int]


def prepare_article_counts_by_source(
    df: pd.DataFrame,
    *,
    require_purchase_date: bool,
) -> Literal["empty"] | Literal["no_source"] | ArticleCountsBySourcePrepared:
    if df.empty:
        return "empty"
    if "article_id" not in df.columns or "source_name" not in df.columns:
        return "no_source"

    work = df.copy()
    if require_purchase_date:
        if PURCHASE_DATE_COL not in work.columns:
            return "no_source"
        purchase_ts = pd.to_datetime(work[PURCHASE_DATE_COL], errors="coerce")
        has_purchase = purchase_ts.notna()
        article_ids_ok = work.loc[has_purchase, "article_id"].dropna().unique()
        work = work[work["article_id"].isin(article_ids_ok)]

    work = work.loc[work["source_name"].notna(), ["article_id", "source_name"]].copy()
    work["source_name"] = work["source_name"].astype(str).str.strip()
    work = work[work["source_name"] != ""]

    if work.empty:
        return "no_source"

    deduped = work.drop_duplicates(subset=["article_id"], keep="first")
    counts = deduped["source_name"].value_counts().sort_values(ascending=False)
    labels = [str(x) for x in counts.index.tolist()]
    values = [int(v) for v in counts.values]
    return ArticleCountsBySourcePrepared(labels=labels, values=values)


def _article_counts_pie_figure(
    prepared: ArticleCountsBySourcePrepared,
    title: str,
) -> go.Figure:
    total = sum(prepared.values)
    fig = go.Figure(
        data=[
            go.Pie(
                labels=prepared.labels,
                values=prepared.values,
                sort=False,
                textinfo="label+percent",
                hovertemplate="%{label}<br>count: %{value}<br>%{percent}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=dict(text=f"{title}<br><sup>Unique articles: {total:,}</sup>", x=0.5, xanchor="center"),
        height=400,
        margin=dict(l=10, r=10, t=70, b=10),
        template="plotly_white",
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5),
    )
    return fig


def render_headlines_by_news_source_charts(df: pd.DataFrame) -> None:
    col_left, col_right = st.columns(2)
    all_prepared = prepare_article_counts_by_source(df, require_purchase_date=False)
    purchase_prepared = prepare_article_counts_by_source(df, require_purchase_date=True)

    with col_left:
        if all_prepared == "empty":
            st.info("No rows match the current filters.")
        elif all_prepared == "no_source":
            st.info("No articles with a news source in the current filter.")
        else:
            fig = _article_counts_pie_figure(
                all_prepared,
                "Articles by source (unique headlines)",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        if purchase_prepared == "empty":
            st.info("No rows match the current filters.")
        elif purchase_prepared == "no_source":
            if PURCHASE_DATE_COL not in df.columns:
                st.info("Purchase date column is missing from the table.")
            else:
                st.info("No articles with a purchase date in the current filter.")
        else:
            fig = _article_counts_pie_figure(
                purchase_prepared,
                "Articles with a purchase date (unique headlines)",
            )
            st.plotly_chart(fig, use_container_width=True)
