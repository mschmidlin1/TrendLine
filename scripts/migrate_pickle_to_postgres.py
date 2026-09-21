#!/usr/bin/env python3
"""One-time pickle snapshot → Postgres load.

Does not import TradeManager / PersistentDataService / NewsScrapingService.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import struct_time
from typing import Any, Callable, Iterable

from psycopg import sql
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.base.datetime_utils import ensure_utc  # noqa: E402
from src.snapshot_migration import migrate_legacy_archived_entry_in_place  # noqa: E402

ENVELOPE_VERSION = 1
TERMINAL_STATUS_VALUES = frozenset({"filled", "canceled", "expired", "rejected"})

TickerLookup = Callable[[str, bool], tuple[str | None, bool]]


@dataclass
class MigrationCounts:
    articles: int = 0
    sentiments: int = 0
    buys: int = 0
    sells: int = 0
    skipped_served_only: list[str] = field(default_factory=list)
    source_names: set[str] = field(default_factory=set)


def unwrap_envelope(data: object) -> object:
    if not isinstance(data, dict) or "version" not in data or "payload" not in data:
        raise ValueError("Invalid snapshot envelope")
    if data["version"] != ENVELOPE_VERSION:
        raise ValueError(f"Unsupported snapshot version: {data['version']}")
    return data["payload"]


def load_snapshot(path: Path) -> object:
    if not path.is_file():
        raise FileNotFoundError(f"Missing snapshot: {path}")
    with open(path, "rb") as f:
        return unwrap_envelope(pickle.load(f))


def tickers_from_pickle(sr: Any) -> list[str]:
    """Split pickled SentimentResponse.ticker (comma-joined) or .tickers list."""
    raw = getattr(sr, "ticker", None)
    if raw is None:
        raw = getattr(sr, "tickers", None)
    if isinstance(raw, (list, tuple)):
        parts = [str(p).strip().upper() for p in raw]
    elif raw is None:
        parts = []
    else:
        parts = [p.strip().upper() for p in str(raw).split(",")]
    return [p for p in parts if p and p != "NONE"]


def sentiment_from_pickle(sr: Any) -> str:
    value = getattr(sr, "sentiment", None)
    if value is None:
        sents = getattr(sr, "sentiments", None)
        if isinstance(sents, (list, tuple)) and sents:
            return str(sents[0])
        return ""
    return str(value)


def is_order_terminal(order: Any) -> bool:
    """Alpaca status in filled/canceled/expired/rejected — not pickle buy_order_terminal."""
    status = getattr(order, "status", None)
    if status is None:
        return False
    value = getattr(status, "value", status)
    if isinstance(value, str):
        return value.lower() in TERMINAL_STATUS_VALUES
    return False


def _enum_value(value: Any) -> Any:
    if value is None:
        return None
    return getattr(value, "value", value)


def order_to_columns(order: Any) -> dict[str, Any]:
    """Same Alpaca columns as TradeManager.archive_buy / archive_sell (linkage omitted)."""
    return {
        "alpaca_order_id": order.id,
        "client_order_id": order.client_order_id,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "submitted_at": order.submitted_at,
        "filled_at": order.filled_at,
        "expired_at": order.expired_at,
        "expires_at": order.expires_at,
        "canceled_at": order.canceled_at,
        "failed_at": order.failed_at,
        "replaced_at": order.replaced_at,
        "replaced_by": order.replaced_by,
        "replaces": order.replaces,
        "asset_id": order.asset_id,
        "symbol": order.symbol,
        "asset_class": _enum_value(order.asset_class),
        "notional": order.notional,
        "qty": order.qty,
        "filled_qty": order.filled_qty,
        "filled_avg_price": order.filled_avg_price,
        "order_class": _enum_value(order.order_class),
        "order_type": _enum_value(order.order_type),
        "type": _enum_value(order.type),
        "side": _enum_value(order.side),
        "time_in_force": _enum_value(order.time_in_force),
        "limit_price": order.limit_price,
        "stop_price": order.stop_price,
        "status": _enum_value(order.status),
        "extended_hours": order.extended_hours,
        "legs": Jsonb(order.legs) if isinstance(order.legs, (dict, list)) else order.legs,
        "trail_percent": order.trail_percent,
        "trail_price": order.trail_price,
        "hwm": order.hwm,
        "position_intent": _enum_value(order.position_intent),
        "ratio_qty": order.ratio_qty,
    }


def _article_entry(entry: dict) -> Any:
    return entry.get("article_entry") or {}


def published_at_from_entry(article: Any) -> datetime | None:
    getter = article.get if hasattr(article, "get") else lambda k, d=None: getattr(article, k, d)
    parsed = getter("published_parsed")
    if isinstance(parsed, struct_time):
        return datetime(
            parsed.tm_year,
            parsed.tm_mon,
            parsed.tm_mday,
            parsed.tm_hour,
            parsed.tm_min,
            parsed.tm_sec,
            tzinfo=timezone.utc,
        )
    return None


def raw_entry_json(article: Any) -> Jsonb:
    if hasattr(article, "keys"):
        payload = dict(article)
    else:
        payload = {}
    return Jsonb(json.loads(json.dumps(payload, default=str)))


def article_row_from_entry(entry: dict, source_id: int) -> dict[str, Any]:
    article = _article_entry(entry)
    getter = article.get if hasattr(article, "get") else lambda k, d=None: getattr(article, k, d)
    sr = entry.get("sentiment_response")
    archived_at = ensure_utc(entry.get("archived_at")) or datetime.now(timezone.utc)
    article_id = entry.get("article_id") or getter("link") or ""
    return {
        "article_id": article_id,
        "source_id": source_id,
        "title": getter("title", "") or "",
        "summary": getter("summary", "") or "",
        "published_at": published_at_from_entry(article),
        "published_raw": getter("published", "") or "",
        "rss_guid": getter("id"),
        "raw_entry": raw_entry_json(article),
        "archived_at": archived_at,
        "sentiment_analyzed_at": archived_at,
        "resulted_in_purchase": bool(entry.get("resulted_in_purchase")),
        "sentiment_raw_response": None if sr is None else getattr(sr, "raw_response", None),
        "sentiment_format_match": None if sr is None else getattr(sr, "format_match", None),
    }


def sentiment_rows_from_entry(
    entry: dict,
    ticker_lookup: TickerLookup | None = None,
) -> list[dict[str, Any]]:
    sr = entry.get("sentiment_response")
    if sr is None:
        return []
    article_id = entry.get("article_id")
    sentiment = sentiment_from_pickle(sr)
    buys = entry.get("buy_orders") or {}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ordinal, ticker in enumerate(tickers_from_pickle(sr)):
        if ticker in seen:
            continue
        seen.add(ticker)
        has_buy = ticker in buys
        company = None
        ticker_valid = has_buy
        if ticker_lookup is not None:
            company, ticker_valid = ticker_lookup(ticker, has_buy)
        rows.append(
            {
                "article_id": article_id,
                "company": company,
                "ticker": ticker,
                "sentiment": sentiment,
                "ticker_valid": bool(ticker_valid),
                "ordinal": ordinal,
            }
        )
    return rows


def served_only_ids(served: Iterable[str], archived_ids: set[str]) -> list[str]:
    extra = set(served) - archived_ids
    return sorted(extra)


class TickerEnricher:
    """Alpaca-backed lookup; falls back to buy-order membership after the first failure."""

    def __init__(self) -> None:
        self._svc = None
        self._failed = False

    def lookup(self, ticker: str, has_buy: bool) -> tuple[str | None, bool]:
        if self._failed:
            return None, has_buy
        try:
            if self._svc is None:
                from src.ticker_service import TickerService

                self._svc = TickerService()
            valid = bool(self._svc.is_tradable_stock_symbol(ticker))
            company = self._svc.lookup_stock_name(ticker) if valid else None
            return company, valid
        except Exception as e:
            self._failed = True
            print(
                f"TickerService unavailable ({type(e).__name__}: {e}). "
                "Falling back to ticker_valid = ticker has a buy_order."
            )
            return None, has_buy


def count_from_entries(entries: list[dict], served: Iterable[str] | None) -> MigrationCounts:
    counts = MigrationCounts()
    archived_ids: set[str] = set()
    for entry in entries:
        migrate_legacy_archived_entry_in_place(entry)
        article_id = entry.get("article_id")
        if article_id:
            archived_ids.add(article_id)
        counts.articles += 1
        counts.sentiments += len(sentiment_rows_from_entry(entry))
        buys = entry.get("buy_orders") or {}
        sells = entry.get("sell_orders") or {}
        for sym, bo in buys.items():
            if bo is None:
                continue
            counts.buys += 1
            so = sells.get(sym)
            if so is not None:
                counts.sells += 1
        name = entry.get("source_name")
        if name:
            counts.source_names.add(name)
    if served is not None:
        counts.skipped_served_only = served_only_ids(served, archived_ids)
    return counts


def load_trade_and_news(data_dir: Path) -> tuple[list[dict], object | None]:
    trade = load_snapshot(data_dir / "trade_lifecycle.snapshot")
    if not isinstance(trade, dict) or "archived_entries" not in trade:
        raise ValueError("trade_lifecycle.snapshot payload missing archived_entries")
    entries = trade["archived_entries"]
    if not isinstance(entries, list):
        raise ValueError("archived_entries must be a list")

    news_path = data_dir / "news_scraper.snapshot"
    served: object | None = None
    if news_path.is_file():
        news = load_snapshot(news_path)
        if isinstance(news, dict):
            served = news.get("served_articles")
    return entries, served


def postgres_conninfo() -> str:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    from src.configs import (
        POSTGRES_DB,
        POSTGRES_HOST,
        POSTGRES_PASSWORD,
        POSTGRES_PORT,
        POSTGRES_USER,
    )

    return (
        f"host={POSTGRES_HOST} "
        f"port={POSTGRES_PORT} "
        f"dbname={POSTGRES_DB} "
        f"user={POSTGRES_USER} "
        f"password={POSTGRES_PASSWORD}"
    )


def _insert_row(
    cur,
    table: str,
    row: dict[str, Any],
    returning: str | None = None,
    on_conflict: str | None = None,
) -> Any:
    columns = list(row.keys())
    values = list(row.values())
    stmt = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({placeholders})").format(
        table=sql.Identifier(table),
        fields=sql.SQL(", ").join(map(sql.Identifier, columns)),
        placeholders=sql.SQL(", ").join(sql.Placeholder() * len(values)),
    )
    extra = sql.SQL("")
    if on_conflict:
        extra = sql.SQL(" ON CONFLICT ({target}) DO NOTHING").format(
            target=sql.SQL(", ").join(sql.Identifier(c.strip()) for c in on_conflict.split(","))
        )
    returning_sql = sql.SQL("")
    if returning:
        returning_sql = sql.SQL(" RETURNING {pk}").format(pk=sql.Identifier(returning))
    cur.execute(stmt + extra + returning_sql, values)
    if returning:
        fetched = cur.fetchone()
        if fetched is None:
            return None
        return fetched[0]
    return None


def seed_news_sources(cur, rss_feeds: dict[str, str], extra_names: Iterable[str]) -> dict[str, int]:
    for name, url in rss_feeds.items():
        cur.execute(
            """
            INSERT INTO news_sources (name, url)
            VALUES (%s, %s)
            ON CONFLICT (url) DO UPDATE
              SET name = EXCLUDED.name,
                  updated_at = now()
            """,
            (name, url),
        )
    for name in extra_names:
        cur.execute("SELECT id FROM news_sources WHERE name = %s LIMIT 1", (name,))
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO news_sources (name, url)
                VALUES (%s, %s)
                ON CONFLICT (url) DO NOTHING
                """,
                (name, f"migrated://{name}"),
            )
    cur.execute("SELECT name, id FROM news_sources")
    by_name: dict[str, int] = {}
    for name, source_id in cur.fetchall():
        by_name.setdefault(name, source_id)
    return by_name


def insert_entry(
    cur,
    entry: dict,
    source_ids: dict[str, int],
    ticker_lookup: TickerLookup,
    force: bool,
) -> None:
    migrate_legacy_archived_entry_in_place(entry)
    source_name = entry.get("source_name")
    if not source_name or source_name not in source_ids:
        raise RuntimeError(f"Unknown news source {source_name!r} for {entry.get('article_id')!r}")
    article_row = article_row_from_entry(entry, source_ids[source_name])
    conflict = "article_id" if force else None
    _insert_row(cur, "articles", article_row, on_conflict=conflict)

    sentiment_id_by_ticker: dict[str, int] = {}
    for sent_row in sentiment_rows_from_entry(entry, ticker_lookup=ticker_lookup):
        sent_conflict = "article_id, ticker" if force else None
        sent_id = _insert_row(
            cur,
            "sentiments",
            sent_row,
            returning="id",
            on_conflict=sent_conflict,
        )
        if sent_id is None and force:
            cur.execute(
                "SELECT id FROM sentiments WHERE article_id = %s AND ticker = %s",
                (sent_row["article_id"], sent_row["ticker"]),
            )
            found = cur.fetchone()
            sent_id = found[0] if found else None
        if sent_id is not None:
            sentiment_id_by_ticker[sent_row["ticker"]] = sent_id

    buys = entry.get("buy_orders") or {}
    sells = entry.get("sell_orders") or {}
    for sym, buy_order in buys.items():
        if buy_order is None:
            continue
        buy_row = {
            "article_id": article_row["article_id"],
            "sentiment_id": sentiment_id_by_ticker.get(str(sym).upper())
            or sentiment_id_by_ticker.get(getattr(buy_order, "symbol", "")),
            "is_terminal": is_order_terminal(buy_order),
            **order_to_columns(buy_order),
        }
        _insert_row(cur, "buy_orders", buy_row, on_conflict="alpaca_order_id" if force else None)
        sell_order = sells.get(sym)
        if sell_order is None:
            continue
        sell_row = {
            "buy_order_id": buy_order.id,
            "is_terminal": is_order_terminal(sell_order),
            **order_to_columns(sell_order),
        }
        _insert_row(cur, "sell_orders", sell_row, on_conflict="alpaca_order_id" if force else None)


def run_migration(
    data_dir: Path,
    dry_run: bool = False,
    force: bool = False,
    ticker_lookup: TickerLookup | None = None,
) -> MigrationCounts:
    entries, served = load_trade_and_news(data_dir)
    counts = count_from_entries(entries, served if isinstance(served, (set, list)) else None)

    print(f"Pickle articles:          {counts.articles}")
    print(f"Pickle sentiments (split): {counts.sentiments}")
    print(f"Pickle buy_orders:        {counts.buys}")
    print(f"Pickle sell_orders:       {counts.sells}")
    print(f"Skipped served-only:      {len(counts.skipped_served_only)}")
    for url in counts.skipped_served_only:
        print(f"  skip {url}")

    if dry_run:
        print("Dry run — no database writes.")
        return counts

    import psycopg
    from src.configs import RSS_FEED_URLS

    enricher = TickerEnricher() if ticker_lookup is None else None
    lookup = ticker_lookup if ticker_lookup is not None else enricher.lookup

    with psycopg.connect(postgres_conninfo()) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT 1 FROM news_sources LIMIT 1")
            except Exception as e:
                raise RuntimeError(
                    "Schema missing. Run: python scripts/apply_schema.py"
                ) from e
            cur.execute("SELECT COUNT(*) FROM articles")
            existing = cur.fetchone()[0]
            if existing and not force:
                raise RuntimeError(
                    f"articles already has {existing} row(s). "
                    "Aborting (pass --force to insert with ON CONFLICT DO NOTHING)."
                )
            source_ids = seed_news_sources(cur, RSS_FEED_URLS, counts.source_names)
            for entry in entries:
                insert_entry(cur, entry, source_ids, lookup, force=force)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM news_sources")
            n_sources = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM articles")
            n_articles = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sentiments")
            n_sent = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM buy_orders")
            n_buys = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sell_orders")
            n_sells = cur.fetchone()[0]

    print("DB after commit:")
    print(f"  news_sources: {n_sources}")
    print(f"  articles:     {n_articles} (pickle {counts.articles})")
    print(f"  sentiments:   {n_sent} (pickle {counts.sentiments})")
    print(f"  buy_orders:   {n_buys} (pickle {counts.buys})")
    print(f"  sell_orders:  {n_sells} (pickle {counts.sells})")
    print(
        "Do not delete persistent_data/. After you are satisfied, rename it:\n"
        "  mv persistent_data persistent_data.bak"
    )
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load pickle snapshots into Postgres")
    parser.add_argument("--data-dir", default="persistent_data", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow insert when articles is non-empty (ON CONFLICT DO NOTHING)",
    )
    args = parser.parse_args(argv)
    data_dir = args.data_dir
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    run_migration(data_dir, dry_run=args.dry_run, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
