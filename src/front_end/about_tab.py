from __future__ import annotations

from datetime import timedelta

import streamlit as st

from src.configs import BASE_PURCHASE_QTY, MARKET_HOLD_TIME, SCRAPE_FREQUENCY, RSS_FEED_URLS



def timedelta_to_nearest_hours(td: timedelta) -> int:
    return round(td.total_seconds() / 3600)
def timedelta_to_nearest_minutes(td: timedelta) -> int:
    return round(td.total_seconds() / 60)

def render_about_doc() -> None:
    scrape_str = timedelta_to_nearest_minutes(SCRAPE_FREQUENCY)
    hold_str = timedelta_to_nearest_hours(MARKET_HOLD_TIME)

    st.markdown(
        f"""
# TrendLine

### Core Principle

TrendLine works based on one main assumption, that news data is highly correlated to market sentiment. TrendLine lets news sentiment influence it's stock buying decisions, very similar to how a human might be influenced by the news. 

The basic workflow of the algorithm is this:
Read news articles -> analyze sentiment -> trade stocks.


### Algorithm Overview

TrendLine works in a cyclical way. In a loop, it:
1. Scrapes for new headlines from specified sources every `{scrape_str}` minutes.
    - The news sources are: `[{", ".join(RSS_FEED_URLS.keys())}]`
2. Analyzes the sentiment of each news headline using an Ollama model.
3. Analyzes the news headlines to see if they are specific to a company.
4. Purchases `{BASE_PURCHASE_QTY}` share(s) for any positive sentiment headline specific to a single company.
5. Holds the shares for `{hold_str}` hour(s).
6. Sells shares after the hold period has expired.


### Finer Points

This algorithm runs continuously (around the clock). Therefore it may find positive sentiment articles posted during market closed hours. In this case, a Market Order is cued for purchase. The hold time of `{hold_str}` hour(s) does not start until the Market Order is filled. 

        """.strip()
    )



    
