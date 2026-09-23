"""Load the news-trades table from Postgres for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from trend_core.database.db_service import DatabaseService

NEWS_TRADE_COLUMNS: tuple[str, ...] = (
    "article_id",
    "source_name",
    "title",
    "link",
    "published_date",
    "summary",
    "sentiment",
    "ticker",
    "format_match",
    "ticker_found",
    "raw_sentiment_response",
    "resulted_in_purchase",
    "has_buy_order",
    "archived_at",
    "buy_order_id",
    "buy_order_symbol",
    "buy_order_qty",
    "buy_order_status",
    "buy_order_filled_at",
    "buy_order_filled_avg_price",
    "buy_order_terminal",
    "sell_order_id",
    "sell_order_symbol",
    "sell_order_qty",
    "sell_order_status",
    "sell_order_filled_at",
    "sell_order_filled_avg_price",
    "sell_order_terminal",
    "company",
)

_QTY_PRICE_COLUMNS = (
    "buy_order_qty",
    "buy_order_filled_avg_price",
    "sell_order_qty",
    "sell_order_filled_avg_price",
)

# One row per sentiment ticker. Articles with no sentiments row (LLM returned None)
# still appear via the left join. Unanalyzed scrapes are excluded.
_NEWS_TRADES_SQL = """
SELECT
    a.article_id,
    ns.name AS source_name,
    a.title,
    a.article_id AS link,
    a.published_raw AS published_date,
    a.summary,
    s.sentiment,
    s.ticker,
    a.sentiment_format_match AS format_match,
    s.ticker_valid AS ticker_found,
    a.sentiment_raw_response AS raw_sentiment_response,
    a.resulted_in_purchase,
    (b.alpaca_order_id IS NOT NULL) AS has_buy_order,
    a.archived_at,
    b.alpaca_order_id::text AS buy_order_id,
    b.symbol AS buy_order_symbol,
    b.qty AS buy_order_qty,
    b.status AS buy_order_status,
    b.filled_at AS buy_order_filled_at,
    b.filled_avg_price AS buy_order_filled_avg_price,
    b.is_terminal AS buy_order_terminal,
    so.alpaca_order_id::text AS sell_order_id,
    so.symbol AS sell_order_symbol,
    so.qty AS sell_order_qty,
    so.status AS sell_order_status,
    so.filled_at AS sell_order_filled_at,
    so.filled_avg_price AS sell_order_filled_avg_price,
    so.is_terminal AS sell_order_terminal,
    s.company AS company
FROM articles a
JOIN news_sources ns ON a.source_id = ns.id
LEFT JOIN sentiments s ON s.article_id = a.article_id
LEFT JOIN buy_orders b ON b.sentiment_id = s.id
LEFT JOIN sell_orders so ON so.buy_order_id = b.alpaca_order_id
WHERE a.sentiment_analyzed_at IS NOT NULL
ORDER BY a.archived_at DESC, s.ordinal ASC NULLS LAST
"""


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _optional_text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return str(value)


def _terminal_flag(value: Any, present: bool) -> bool:
    if not present or _is_missing(value):
        return True
    return bool(value)


def rows_to_news_trades_dataframe(rows: Sequence[Sequence[Any]]) -> pd.DataFrame:
    """Shape query tuples into the legacy news-trades columns."""
    frame = pd.DataFrame.from_records(list(rows), columns=list(NEWS_TRADE_COLUMNS))
    if frame.empty:
        return frame

    frame["buy_order_id"] = frame["buy_order_id"].map(_optional_text)
    frame["sell_order_id"] = frame["sell_order_id"].map(_optional_text)
    has_buy = frame["buy_order_id"].notna()
    has_sell = frame["sell_order_id"].notna()
    frame["has_buy_order"] = has_buy.to_numpy()
    frame["buy_order_terminal"] = [
        _terminal_flag(value, present)
        for value, present in zip(frame["buy_order_terminal"], has_buy, strict=True)
    ]
    frame["sell_order_terminal"] = [
        _terminal_flag(value, present)
        for value, present in zip(frame["sell_order_terminal"], has_sell, strict=True)
    ]
    for column in _QTY_PRICE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _ensure_database_open(db: DatabaseService) -> None:
    # open() replaces _conn without closing it, so only connect when needed.
    conn = db._conn
    if conn is None or conn.closed:
        db.open()


def load_news_trades_dataframe() -> pd.DataFrame:
    """Return analyzed articles joined to sentiments and orders."""
    db = DatabaseService()
    _ensure_database_open(db)
    rows = db.fetch_all(_NEWS_TRADES_SQL)
    return rows_to_news_trades_dataframe(rows)
