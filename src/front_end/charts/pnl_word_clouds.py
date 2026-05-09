from __future__ import annotations

from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from wordcloud import STOPWORDS, WordCloud


def prepare_article_pnl_buckets(
    df: pd.DataFrame,
) -> Literal["empty"] | Literal["missing_columns"] | tuple[str, str]:
    if df.empty:
        return "empty"
    required = ("article_id", "Headline", "Total Gain")
    if not all(c in df.columns for c in required):
        return "missing_columns"

    work = df.loc[df["article_id"].notna()].copy()
    if work.empty:
        return "empty"

    gain = pd.to_numeric(work["Total Gain"], errors="coerce")
    work["_tg"] = gain

    agg = work.groupby("article_id", as_index=False).agg(
        net_pnl=("_tg", "sum"),
        Headline=("Headline", "first"),
    )
    net = agg["net_pnl"].to_numpy(dtype=float, copy=True)
    ok = np.isfinite(net)
    agg = agg.loc[ok]

    def _corpus_for(mask: pd.Series) -> str:
        heads = agg.loc[mask, "Headline"].dropna().astype(str).str.strip()
        heads = heads[heads != ""]
        return " ".join(heads.tolist())

    winners = agg["net_pnl"] > 0
    losers = agg["net_pnl"] < 0
    return (_corpus_for(winners), _corpus_for(losers))


def _wordcloud_figure(text: str) -> plt.Figure:
    wc = WordCloud(
        width=800,
        height=400,
        background_color="white",
        stopwords=STOPWORDS,
        colormap="viridis",
    ).generate(text)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout()
    return fig


def render_pnl_word_cloud_charts(df: pd.DataFrame) -> None:
    prepared = prepare_article_pnl_buckets(df)
    if prepared == "empty":
        st.info("No rows match the current filters.")
        return
    if prepared == "missing_columns":
        st.info("Cannot build word clouds: expected article_id, Headline, and Total Gain.")
        return

    winners_text, losers_text = prepared
    st.caption(
        "Net PnL is summed per article when an article has multiple tickers. "
        "Same filters as the table and the same sign convention as “Pos Vs Neg Trades”."
    )

    col_win, col_lose = st.columns(2)
    with col_win:
        st.markdown("**Made money (net PnL > 0)**")
        if winners_text.strip():
            fig = _wordcloud_figure(winners_text)
            st.pyplot(fig, clear_figure=True)
            plt.close(fig)
        else:
            st.info("No winning articles in the current filter.")
    with col_lose:
        st.markdown("**Lost money (net PnL < 0)**")
        if losers_text.strip():
            fig = _wordcloud_figure(losers_text)
            st.pyplot(fig, clear_figure=True)
            plt.close(fig)
        else:
            st.info("No losing articles in the current filter.")
