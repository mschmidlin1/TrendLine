import pandas as pd
from typing import List
from alpaca.trading.models import Order, Position
from feedparser.util import FeedParserDict
from datetime import datetime

def orders_to_dataframe(orders: List[Order]) -> pd.DataFrame:
    """
    Converts a list of orders to a dataframe. Preserves as types as much as possible.
    """
    order_dicts = [order.model_dump() for order in orders]
    
    df = pd.DataFrame(order_dicts)
    
    if df.empty:
        return df

    # Ensure datetime objects are properly typed in Pandas
    # Alpaca's pydantic models usually handle the initial conversion, 
    # but this ensures the Series is in datetime64[ns] format.
    datetime_cols = [col for col in df.columns if "_at" in col]
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])


    non_datetime_cols = df.drop(columns=datetime_cols).columns


    numeric_cols = []
    for col in non_datetime_cols:
        # 1. Try to convert the column
        converted = pd.to_numeric(df[col], errors='coerce')
        
        # 2. Check: Does it have non-null values, 
        # and are the only NaNs the ones that were already NaN?
        if converted.notna().any() and (converted.isna() == df[col].isna()).all():
            numeric_cols.append(col)
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)

    return df

def positions_to_dataframe(orders: List[Position]) -> pd.DataFrame:
    """
    Converts a list of orders to a dataframe. Preserves as types as much as possible.
    """
    order_dicts = [order.model_dump() for order in orders]
    
    df = pd.DataFrame(order_dicts)
    
    if df.empty:
        return df

    # Ensure datetime objects are properly typed in Pandas
    # Alpaca's pydantic models usually handle the initial conversion, 
    # but this ensures the Series is in datetime64[ns] format.
    datetime_cols = [col for col in df.columns if "_at" in col]
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])


    non_datetime_cols = df.drop(columns=datetime_cols).columns


    numeric_cols = []
    for col in non_datetime_cols:
        # 1. Try to convert the column
        converted = pd.to_numeric(df[col], errors='coerce')
        
        # 2. Check: Does it have non-null values, 
        # and are the only NaNs the ones that were already NaN?
        if converted.notna().any() and (converted.isna() == df[col].isna()).all():
            numeric_cols.append(col)
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)

    return df


def feedparser_to_df(feed: FeedParserDict) -> pd.DataFrame:
    """
    Convert a feed to a pandas dataframe
    """
    articles = []
    
    # Extract feed-level metadata
    company_name = feed.get('title', 'Unknown Source')
    feed_url = feed.get('href', '')

    for entry in feed.entries:
        article_data = {
            # Core Info
            "company": company_name,
            "feed_url": feed_url,
            "date": entry.get('published', entry.get('updated', '')),
            "headline": entry.get('title', ''),
            "content": entry.get('description', ''),
            
            # Useful for Trading & Automation
            "link": entry.get('link', ''),
            "summary": entry.get('summary', ''),
            "tags": [tag.term for tag in entry.get('tags', [])] if 'tags' in entry else [],
        }
        articles.append(article_data)

    df = pd.DataFrame(articles)

    # Clean up the date to a proper datetime object
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        # Sort by date descending so newest info is on top
        df = df.sort_values(by='date', ascending=False).reset_index(drop=True)

    return df



















