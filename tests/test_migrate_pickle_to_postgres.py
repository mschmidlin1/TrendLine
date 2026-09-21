import importlib.util
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


def _order(symbol="NVDA", status=OrderStatus.FILLED, order_id=None):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
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

    def test_served_only_skipped(self):
        archived = {"https://example.com/a"}
        served = {"https://example.com/a", "https://example.com/only-served"}
        skipped = migrator.served_only_ids(served, archived)
        self.assertEqual(skipped, ["https://example.com/only-served"])

    def test_filled_is_terminal_even_if_pickle_flag_false(self):
        order = _order(status=OrderStatus.FILLED)
        self.assertTrue(migrator.is_order_terminal(order))
        entry = _entry(buy=order)
        self.assertFalse(entry["buy_order_terminal"][order.symbol])

    def test_new_order_not_terminal(self):
        self.assertFalse(migrator.is_order_terminal(_order(status=OrderStatus.NEW)))

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
        self.assertEqual(counts.skipped_served_only, ["https://skip"])


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
class TestMigratePostgres(unittest.TestCase):
    def test_tiny_synthetic_snapshot(self):
        import psycopg

        article_id = f"https://example.test/migrate-unit/{uuid4()}"
        buy = _order(symbol="NVDA")
        sell = _order(symbol="NVDA")
        entry = _entry(article_id=article_id, ticker="NVDA,GLW", buy=buy, sell=sell)
        payload = {
            "archived_entries": [entry],
            "_article_id_index": {},
            "_buy_order_id_index": {},
            "ready_to_sell": [],
        }
        news_payload = {
            "rss_feeds": {},
            "served_articles": {article_id, "https://example.test/served-only"},
            "news_data": {},
        }
        tmp = tempfile.mkdtemp()
        data_dir = Path(tmp)
        with open(data_dir / "trade_lifecycle.snapshot", "wb") as f:
            pickle.dump({"version": 1, "payload": payload}, f)
        with open(data_dir / "news_scraper.snapshot", "wb") as f:
            pickle.dump({"version": 1, "payload": news_payload}, f)

        def lookup(ticker, has_buy):
            return f"Co-{ticker}", ticker == "NVDA"

        try:
            migrator.run_migration(data_dir, dry_run=False, force=True, ticker_lookup=lookup)
            with psycopg.connect(migrator.postgres_conninfo()) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT title, resulted_in_purchase FROM articles WHERE article_id = %s", (article_id,))
                    row = cur.fetchone()
                    self.assertIsNotNone(row)
                    self.assertEqual(row[0], "Hello")
                    self.assertTrue(row[1])
                    cur.execute("SELECT ticker FROM sentiments WHERE article_id = %s ORDER BY ordinal", (article_id,))
                    self.assertEqual([r[0] for r in cur.fetchall()], ["NVDA", "GLW"])
                    cur.execute(
                        "SELECT alpaca_order_id, sentiment_id FROM buy_orders WHERE article_id = %s",
                        (article_id,),
                    )
                    buy_row = cur.fetchone()
                    self.assertEqual(buy_row[0], buy.id)
                    self.assertIsNotNone(buy_row[1])
                    cur.execute(
                        "SELECT buy_order_id FROM sell_orders WHERE alpaca_order_id = %s",
                        (sell.id,),
                    )
                    self.assertEqual(cur.fetchone()[0], buy.id)
                    cur.execute("SELECT 1 FROM articles WHERE article_id = %s", ("https://example.test/served-only",))
                    self.assertIsNone(cur.fetchone())
        finally:
            with psycopg.connect(migrator.postgres_conninfo()) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM sell_orders WHERE alpaca_order_id = %s", (sell.id,))
                    cur.execute("DELETE FROM buy_orders WHERE article_id = %s", (article_id,))
                    cur.execute("DELETE FROM articles WHERE article_id = %s", (article_id,))
                conn.commit()


if __name__ == "__main__":
    unittest.main()
