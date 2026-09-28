import importlib.util
import json
import pickle
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from alpaca.trading.enums import OrderStatus

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "migrate_pickle_to_postgres.py"
_spec = importlib.util.spec_from_file_location("migrate_pickle_to_postgres", _SCRIPT)
migrator = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["migrate_pickle_to_postgres"] = migrator
_spec.loader.exec_module(migrator)


def _sentiment(sentiment="positive", ticker="NVDA,GLW", format_match=True, raw="Positive | NVDA,GLW"):
    return SimpleNamespace(
        sentiment=sentiment,
        ticker=ticker,
        format_match=format_match,
        ticker_found=True,
        raw_response=raw,
    )


class _FakeOrder(SimpleNamespace):
    def model_dump_json(self):
        return json.dumps(
            {
                "id": str(self.id),
                "symbol": self.symbol,
                "status": self.status.value if hasattr(self.status, "value") else self.status,
                "side": self.side.value if hasattr(self.side, "value") else self.side,
            }
        )


def _order(symbol="NVDA", status=OrderStatus.FILLED, order_id=None):
    now = datetime.now(timezone.utc)
    return _FakeOrder(
        id=order_id or uuid4(),
        client_order_id="cid",
        created_at=now,
        updated_at=now,
        submitted_at=now,
        filled_at=now,
        expired_at=None,
        expires_at=None,
        canceled_at=None,
        failed_at=None,
        replaced_at=None,
        replaced_by=None,
        replaces=None,
        asset_id=uuid4(),
        symbol=symbol,
        asset_class=SimpleNamespace(value="us_equity"),
        notional=None,
        qty="1",
        filled_qty="1",
        filled_avg_price="10.0",
        order_class=SimpleNamespace(value="simple"),
        order_type=SimpleNamespace(value="market"),
        type=SimpleNamespace(value="market"),
        side=SimpleNamespace(value="buy"),
        time_in_force=SimpleNamespace(value="gtc"),
        limit_price=None,
        stop_price=None,
        status=status,
        extended_hours=False,
        legs=None,
        trail_percent=None,
        trail_price=None,
        hwm=None,
        position_intent=SimpleNamespace(value="buy_to_open"),
        ratio_qty=None,
    )


def _entry(article_id="https://example.com/a", ticker="NVDA", buy=None, sell=None):
    archived = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    buys = {}
    sells = {}
    if buy is not None:
        buys[buy.symbol] = buy
        sells[buy.symbol] = sell
    return {
        "article_id": article_id,
        "source_name": "CNBC",
        "article_entry": {
            "title": "Hello",
            "link": article_id,
            "summary": "sum",
            "published": "Wed, 01 Apr 2026 12:00:00 GMT",
            "id": article_id,
        },
        "sentiment_response": _sentiment(ticker=ticker),
        "buy_orders": buys,
        "sell_orders": sells,
        "buy_order_terminal": {buy.symbol: False} if buy is not None else {},
        "sell_order_terminal": {},
        "resulted_in_purchase": bool(buys),
        "archived_at": archived,
    }


class TestMigrateTransforms(unittest.TestCase):
    def test_tickers_split_and_skip_none(self):
        self.assertEqual(migrator.tickers_from_pickle(_sentiment(ticker="NVDA,GLW")), ["NVDA", "GLW"])
        self.assertEqual(migrator.tickers_from_pickle(_sentiment(ticker="NONE")), [])
        self.assertEqual(migrator.tickers_from_pickle(_sentiment(ticker="")), [])
        self.assertEqual(migrator.tickers_from_pickle(_sentiment(ticker="nvda, none, glw")), ["NVDA", "GLW"])

    def test_article_row_sets_sentiment_analyzed_at(self):
        entry = _entry()
        row = migrator.article_row_from_entry(entry, source_id=1)
        self.assertEqual(row["sentiment_analyzed_at"], entry["archived_at"])
        self.assertEqual(row["archived_at"], entry["archived_at"])
        self.assertEqual(row["article_id"], "https://example.com/a")
        self.assertEqual(row["title"], "Hello")
        self.assertNotIn("resulted_in_purchase", row)

    def test_orders_and_trades_from_buy_and_leftover(self):
        buy = _order(symbol="NVDA")
        sell = _order(symbol="NVDA")
        sell.side = type("Side", (), {"value": "sell"})()
        entry = _entry(ticker="NVDA,GLW,F", buy=buy, sell=sell)
        sent_rows = migrator.sentiment_rows_from_entry(
            entry,
            ticker_lookup=lambda ticker, has_buy: (None, ticker in {"NVDA", "GLW"}),
        )

        order_rows = migrator.order_rows_from_entry(entry)
        self.assertEqual(len(order_rows), 2)
        self.assertEqual(order_rows[0]["side"], "buy")
        self.assertEqual(order_rows[1]["side"], "sell")
        self.assertEqual(order_rows[0]["alpaca_order_id"], buy.id)
        self.assertEqual(order_rows[1]["alpaca_order_id"], sell.id)
        for row in order_rows:
            self.assertIn("raw", row)
            self.assertIsNotNone(row["raw"])
            self.assertNotIn("is_terminal", row)

        trades = migrator.trade_rows_from_entry(entry, sent_rows)
        by_symbol = {row["symbol"]: row for row in trades}
        self.assertEqual(set(by_symbol), {"NVDA", "GLW"})
        self.assertEqual(by_symbol["NVDA"]["buy_order_id"], buy.id)
        self.assertEqual(by_symbol["NVDA"]["sell_order_id"], sell.id)
        self.assertIsNone(by_symbol["NVDA"]["buy_failure_reason"])
        self.assertEqual(
            by_symbol["GLW"]["buy_failure_reason"],
            migrator.MIGRATED_BUY_FAILURE_REASON,
        )
        self.assertIsNone(by_symbol["GLW"]["buy_order_id"])
        self.assertNotIn("F", by_symbol)

    def test_served_only_skipped(self):
        archived = {"https://example.com/a"}
        served = {"https://example.com/a", "https://example.com/only-served"}
        skipped = migrator.served_only_ids(served, archived)
        self.assertEqual(skipped, ["https://example.com/only-served"])

    def test_count_from_entries(self):
        buy = _order()
        sell = _order(symbol="NVDA", status=OrderStatus.FILLED)
        entries = [
            _entry(article_id="https://example.com/a", ticker="NVDA,GLW", buy=buy, sell=sell),
            _entry(article_id="https://example.com/b", ticker="NONE"),
        ]
        counts = migrator.count_from_entries(
            entries, served={"https://example.com/a", "https://example.com/b", "https://skip"}
        )
        self.assertEqual(counts.articles, 2)
        self.assertEqual(counts.sentiments, 2)
        self.assertEqual(counts.buys, 1)
        self.assertEqual(counts.sells, 1)
        self.assertEqual(counts.placeholder_trades, 0)
        self.assertEqual(counts.skipped_served_only, ["https://skip"])

        leftover_counts = migrator.count_from_entries(
            [_entry(article_id="https://example.com/a", ticker="NVDA,GLW", buy=buy, sell=sell)],
            served=None,
            ticker_lookup=lambda ticker, has_buy: (None, True),
        )
        self.assertEqual(leftover_counts.placeholder_trades, 1)


def _postgres_available() -> bool:
    try:
        import psycopg
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env", override=False)
        from trend_core.configs import (
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
class TestMigratePostgres(unittest.TestCase):
    def test_tiny_synthetic_snapshot(self):
        import psycopg

        article_id = f"https://example.test/migrate-unit/{uuid4()}"
        leftover_id = f"https://example.test/migrate-unit/{uuid4()}"
        buy = _order(symbol="NVDA")
        sell = _order(symbol="NVDA")
        entry = _entry(article_id=article_id, ticker="NVDA,GLW", buy=buy, sell=sell)
        leftover = _entry(article_id=leftover_id, ticker="AAPL")
        payload = {
            "archived_entries": [entry, leftover],
            "_article_id_index": {},
            "_buy_order_id_index": {},
            "ready_to_sell": [],
        }
        news_payload = {
            "rss_feeds": {},
            "served_articles": {article_id, leftover_id, "https://example.test/served-only"},
            "news_data": {},
        }
        tmp = tempfile.mkdtemp()
        data_dir = Path(tmp)
        with open(data_dir / "trade_lifecycle.snapshot", "wb") as f:
            pickle.dump({"version": 1, "payload": payload}, f)
        with open(data_dir / "news_scraper.snapshot", "wb") as f:
            pickle.dump({"version": 1, "payload": news_payload}, f)

        def lookup(ticker, has_buy):
            return f"Co-{ticker}", ticker in {"NVDA", "AAPL"}

        try:
            # NVDA buy+sell; GLW invalid leftover (no trade); AAPL valid leftover (failure row).
            migrator.run_migration(data_dir, dry_run=False, force=True, ticker_lookup=lookup)
            with psycopg.connect(migrator.postgres_conninfo()) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT title FROM articles WHERE article_id = %s", (article_id,))
                    row = cur.fetchone()
                    self.assertIsNotNone(row)
                    self.assertEqual(row[0], "Hello")
                    cur.execute("SELECT ticker FROM sentiments WHERE article_id = %s ORDER BY ordinal", (article_id,))
                    self.assertEqual([r[0] for r in cur.fetchall()], ["NVDA", "GLW"])
                    cur.execute(
                        """
                        SELECT side, raw IS NOT NULL
                        FROM orders
                        WHERE alpaca_order_id IN (%s, %s)
                        ORDER BY side
                        """,
                        (buy.id, sell.id),
                    )
                    order_rows = cur.fetchall()
                    self.assertEqual(order_rows, [("buy", True), ("sell", True)])
                    cur.execute(
                        """
                        SELECT t.symbol, t.buy_order_id, t.sell_order_id, t.buy_failure_reason
                        FROM trades t
                        WHERE t.article_id = %s
                        ORDER BY t.symbol
                        """,
                        (article_id,),
                    )
                    nvda_trade = cur.fetchone()
                    self.assertEqual(nvda_trade[0], "NVDA")
                    self.assertEqual(nvda_trade[1], buy.id)
                    self.assertEqual(nvda_trade[2], sell.id)
                    self.assertIsNone(nvda_trade[3])
                    self.assertIsNone(cur.fetchone())
                    cur.execute(
                        """
                        SELECT buy_order_id, buy_failure_reason
                        FROM trades
                        WHERE article_id = %s AND symbol = 'AAPL'
                        """,
                        (leftover_id,),
                    )
                    placeholder = cur.fetchone()
                    self.assertIsNotNone(placeholder)
                    self.assertIsNone(placeholder[0])
                    self.assertEqual(placeholder[1], migrator.MIGRATED_BUY_FAILURE_REASON)
                    cur.execute("SELECT 1 FROM articles WHERE article_id = %s", ("https://example.test/served-only",))
                    self.assertIsNone(cur.fetchone())
        finally:
            with psycopg.connect(migrator.postgres_conninfo()) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM trades WHERE article_id IN (%s, %s)",
                        (article_id, leftover_id),
                    )
                    cur.execute(
                        "DELETE FROM orders WHERE alpaca_order_id IN (%s, %s)",
                        (buy.id, sell.id),
                    )
                    cur.execute(
                        "DELETE FROM articles WHERE article_id IN (%s, %s)",
                        (article_id, leftover_id),
                    )
                conn.commit()


if __name__ == "__main__":
    unittest.main()
