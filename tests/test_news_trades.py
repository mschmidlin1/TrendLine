"""Tests for the dashboard news-trades Postgres read model."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "streamlit-dash"))

from front_end.news_trades import NEWS_TRADE_COLUMNS, load_news_trades_dataframe, rows_to_news_trades_dataframe
from src.lib.database.db_service import DatabaseService

_ROOT = Path(__file__).resolve().parents[1]


def _row(**overrides: object) -> tuple:
    values = {
        "article_id": "https://example.test/article",
        "source_name": "CNBC",
        "title": "NVIDIA rallies",
        "link": "https://example.test/article",
        "published_date": "Tue, 02 Jan 2024 12:00:00 GMT",
        "summary": "A summary",
        "sentiment": "positive",
        "ticker": "NVDA",
        "format_match": True,
        "ticker_found": True,
        "raw_sentiment_response": "Positive | NVDA",
        "resulted_in_purchase": True,
        "has_buy_order": True,
        "archived_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
        "buy_order_id": "11111111-1111-1111-1111-111111111111",
        "buy_order_symbol": "NVDA",
        "buy_order_qty": Decimal("3"),
        "buy_order_status": "filled",
        "buy_order_filled_at": datetime(2024, 1, 3, tzinfo=timezone.utc),
        "buy_order_filled_avg_price": Decimal("100.5"),
        "buy_order_terminal": True,
        "sell_order_id": "22222222-2222-2222-2222-222222222222",
        "sell_order_symbol": "NVDA",
        "sell_order_qty": Decimal("3"),
        "sell_order_status": "filled",
        "sell_order_filled_at": datetime(2024, 1, 4, tzinfo=timezone.utc),
        "sell_order_filled_avg_price": Decimal("110"),
        "sell_order_terminal": True,
        "company": "NVIDIA",
    }
    values.update(overrides)
    return tuple(values[column] for column in NEWS_TRADE_COLUMNS)


class NewsTradesFrameTests(unittest.TestCase):
    def test_filled_round_trip_row(self) -> None:
        frame = rows_to_news_trades_dataframe([_row()])
        self.assertEqual(list(frame.columns), list(NEWS_TRADE_COLUMNS))
        row = frame.iloc[0]
        self.assertEqual(row["article_id"], row["link"])
        self.assertEqual(row["source_name"], "CNBC")
        self.assertEqual(row["sentiment"], "positive")
        self.assertEqual(row["ticker"], "NVDA")
        self.assertEqual(row["company"], "NVIDIA")
        self.assertTrue(row["format_match"])
        self.assertTrue(row["ticker_found"])
        self.assertTrue(row["has_buy_order"])
        self.assertTrue(row["buy_order_terminal"])
        self.assertTrue(row["sell_order_terminal"])
        self.assertEqual(row["buy_order_status"], "filled")
        self.assertEqual(float(row["buy_order_qty"]), 3.0)
        self.assertEqual(float(row["buy_order_filled_avg_price"]), 100.5)
        self.assertEqual(float(row["sell_order_qty"]), 3.0)
        self.assertEqual(float(row["sell_order_filled_avg_price"]), 110.0)

    def test_open_buy_without_sell_stays_non_terminal(self) -> None:
        frame = rows_to_news_trades_dataframe([
            _row(
                sell_order_id=None,
                sell_order_symbol=None,
                sell_order_qty=None,
                sell_order_status=None,
                sell_order_filled_at=None,
                sell_order_filled_avg_price=None,
                sell_order_terminal=None,
                buy_order_terminal=False,
            )
        ])
        row = frame.iloc[0]
        self.assertTrue(row["has_buy_order"])
        self.assertFalse(row["buy_order_terminal"])
        self.assertTrue(row["sell_order_terminal"])
        self.assertTrue(pd.isna(row["sell_order_id"]))
        self.assertTrue(pd.isna(row["sell_order_qty"]))

    def test_article_without_sentiment_row(self) -> None:
        frame = rows_to_news_trades_dataframe([
            _row(
                title="No ticker",
                sentiment=None,
                ticker=None,
                ticker_found=None,
                raw_sentiment_response="None",
                resulted_in_purchase=False,
                has_buy_order=False,
                buy_order_id=None,
                buy_order_symbol=None,
                buy_order_qty=None,
                buy_order_status=None,
                buy_order_filled_at=None,
                buy_order_filled_avg_price=None,
                buy_order_terminal=None,
                sell_order_id=None,
                sell_order_symbol=None,
                sell_order_qty=None,
                sell_order_status=None,
                sell_order_filled_at=None,
                sell_order_filled_avg_price=None,
                sell_order_terminal=None,
                company=None,
            )
        ])
        row = frame.iloc[0]
        self.assertEqual(row["title"], "No ticker")
        self.assertEqual(row["raw_sentiment_response"], "None")
        self.assertTrue(pd.isna(row["ticker"]))
        self.assertTrue(pd.isna(row["sentiment"]))
        self.assertTrue(pd.isna(row["company"]))
        self.assertFalse(row["has_buy_order"])
        self.assertTrue(row["buy_order_terminal"])
        self.assertTrue(row["sell_order_terminal"])

    def test_empty_result_keeps_columns(self) -> None:
        frame = rows_to_news_trades_dataframe([])
        self.assertEqual(len(frame), 0)
        self.assertEqual(list(frame.columns), list(NEWS_TRADE_COLUMNS))


def _postgres_available() -> bool:
    try:
        import psycopg
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env", override=False)
        from src.lib.configs import (
            POSTGRES_DB,
            POSTGRES_HOST,
            POSTGRES_PASSWORD,
            POSTGRES_PORT,
            POSTGRES_USER,
        )

        conninfo = (
            f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} "
            f"user={POSTGRES_USER} password={POSTGRES_PASSWORD}"
        )
        with psycopg.connect(conninfo, connect_timeout=3) as conn:
            conn.execute("SELECT 1 FROM articles LIMIT 1")
        return True
    except Exception:
        return False


@unittest.skipUnless(_postgres_available(), "local Postgres with schema not available")
class NewsTradesPostgresTests(unittest.TestCase):
    def test_load_joins_analyzed_articles(self) -> None:
        import psycopg
        from psycopg.types.json import Jsonb

        from src.lib.configs import (
            POSTGRES_DB,
            POSTGRES_HOST,
            POSTGRES_PASSWORD,
            POSTGRES_PORT,
            POSTGRES_USER,
        )

        source_url = f"https://example.test/dash-feed/{uuid4()}"
        traded_id = f"https://example.test/dash/{uuid4()}"
        plain_id = f"https://example.test/dash/{uuid4()}"
        pending_id = f"https://example.test/dash/{uuid4()}"
        buy_id = uuid4()
        sell_id = uuid4()
        analyzed_at = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
        conninfo = (
            f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} "
            f"user={POSTGRES_USER} password={POSTGRES_PASSWORD}"
        )

        with psycopg.connect(conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO news_sources (name, url) VALUES (%s, %s) RETURNING id",
                    ("Dash Test", source_url),
                )
                source_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO articles (
                        article_id, source_id, title, summary, published_raw, raw_entry,
                        archived_at, sentiment_analyzed_at, resulted_in_purchase,
                        sentiment_raw_response, sentiment_format_match
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        traded_id,
                        source_id,
                        "NVIDIA rallies",
                        "A summary",
                        "Tue, 02 Jan 2024 12:00:00 GMT",
                        Jsonb({"title": "NVIDIA rallies"}),
                        datetime(2024, 1, 2, tzinfo=timezone.utc),
                        analyzed_at,
                        True,
                        "Positive | NVDA",
                        True,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO sentiments (
                        article_id, company, ticker, sentiment, ticker_valid, ordinal, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        traded_id,
                        "NVIDIA",
                        "NVDA",
                        "positive",
                        True,
                        0,
                        analyzed_at,
                    ),
                )
                sentiment_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO buy_orders (
                        article_id, sentiment_id, is_terminal, alpaca_order_id, symbol,
                        qty, filled_avg_price, filled_at, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        traded_id,
                        sentiment_id,
                        True,
                        buy_id,
                        "NVDA",
                        Decimal("3"),
                        Decimal("100.5"),
                        datetime(2024, 1, 3, tzinfo=timezone.utc),
                        "filled",
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO sell_orders (
                        buy_order_id, is_terminal, alpaca_order_id, symbol,
                        qty, filled_avg_price, filled_at, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        buy_id,
                        True,
                        sell_id,
                        "NVDA",
                        Decimal("3"),
                        Decimal("110"),
                        datetime(2024, 1, 4, tzinfo=timezone.utc),
                        "filled",
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO articles (
                        article_id, source_id, title, raw_entry, archived_at,
                        sentiment_analyzed_at, resulted_in_purchase,
                        sentiment_raw_response, sentiment_format_match
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        plain_id,
                        source_id,
                        "No ticker",
                        Jsonb({"title": "No ticker"}),
                        datetime(2024, 6, 1, tzinfo=timezone.utc),
                        analyzed_at,
                        False,
                        "None",
                        True,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO articles (
                        article_id, source_id, title, raw_entry, archived_at, resulted_in_purchase
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        pending_id,
                        source_id,
                        "Still pending",
                        Jsonb({"title": "Still pending"}),
                        datetime(2024, 7, 1, tzinfo=timezone.utc),
                        False,
                    ),
                )
            conn.commit()

        try:
            frame = load_news_trades_dataframe()
            ours = frame[frame["article_id"].isin([traded_id, plain_id, pending_id])]
            self.assertEqual(set(ours["article_id"]), {traded_id, plain_id})

            traded = ours[ours["article_id"] == traded_id].iloc[0]
            self.assertEqual(traded["source_name"], "Dash Test")
            self.assertEqual(traded["link"], traded_id)
            self.assertEqual(traded["ticker"], "NVDA")
            self.assertEqual(traded["company"], "NVIDIA")
            self.assertEqual(traded["sentiment"], "positive")
            self.assertTrue(traded["has_buy_order"])
            self.assertEqual(traded["buy_order_id"], str(buy_id))
            self.assertEqual(traded["sell_order_id"], str(sell_id))
            self.assertEqual(float(traded["buy_order_qty"]), 3.0)
            self.assertEqual(float(traded["buy_order_filled_avg_price"]), 100.5)
            self.assertEqual(float(traded["sell_order_filled_avg_price"]), 110.0)
            self.assertTrue(traded["buy_order_terminal"])
            self.assertTrue(traded["sell_order_terminal"])

            plain = ours[ours["article_id"] == plain_id].iloc[0]
            self.assertEqual(plain["title"], "No ticker")
            self.assertEqual(plain["raw_sentiment_response"], "None")
            self.assertTrue(pd.isna(plain["ticker"]))
            self.assertTrue(pd.isna(plain["company"]))
            self.assertFalse(plain["has_buy_order"])
            self.assertTrue(plain["buy_order_terminal"])
            self.assertTrue(plain["sell_order_terminal"])
        finally:
            DatabaseService().close()
            with psycopg.connect(conninfo) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM sell_orders WHERE alpaca_order_id = %s", (sell_id,))
                    cur.execute("DELETE FROM buy_orders WHERE alpaca_order_id = %s", (buy_id,))
                    cur.execute(
                        "DELETE FROM sentiments WHERE article_id = ANY(%s)",
                        ([traded_id, plain_id, pending_id],),
                    )
                    cur.execute(
                        "DELETE FROM articles WHERE article_id = ANY(%s)",
                        ([traded_id, plain_id, pending_id],),
                    )
                    cur.execute("DELETE FROM news_sources WHERE url = %s", (source_url,))
                conn.commit()


if __name__ == "__main__":
    unittest.main()
