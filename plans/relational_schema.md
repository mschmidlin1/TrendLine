# Relational Schema Proposal for TrendLine

## Stack (locked in)

- **Database engine:** PostgreSQL
- **Python access:** plain SQL + psycopg3 (DDL in `.sql` files; no ORM)
- **Connection:** env / secrets (same pattern as Alpaca keys in `.streamlit/secrets.toml`)
- **Hosting:** local install, Docker, or managed Postgres — not decided yet

## Current state (what we are replacing)

Today durable state is two pickle files under [`persistent_data/`](../persistent_data/):

| Snapshot | Contents |
|----------|----------|
| `trade_lifecycle.snapshot` | `archived_entries[]` + `_article_id_index` + `_buy_order_id_index` + `ready_to_sell` |
| `news_scraper.snapshot` | `rss_feeds` + `served_articles` + `news_data` (last feedparser payloads) |

Natural keys already in use:

- **Article** = RSS `link` URL (`article_id`)
- **Buy/sell order** = Alpaca `Order.id` (UUID)
- **Ticker** = symbol string
- **News source** = config name (`NPR`, `CNBC`, …)

**Keep live/in-memory (not in the DB):** Alpaca account/positions/equity, `TimingService` scrape clock, `TickerService` asset cache, market clock, and RSS conditional-GET validators (`etag` / `modified` on each feed). On process restart, do a full fetch once; within a run, keep etag/modified in memory for 304 short-circuiting.

Scale today is ~7.6k articles / ~580 buys — schema can be simple.

---

## Pipeline change: archive at discovery (no `served_articles`)

Today the scraper marks a URL “served” before the trade manager archives it, which is why a separate dedupe set exists. **Under the relational design we change that flow:**

1. Scrape RSS → find links not already in `articles`
2. **Insert the `articles` row immediately** (discovery = archive)
3. Run sentiment → insert `sentiments` (+ buys when positive)
4. Later: sell lifecycle via `buy_orders` / `sell_orders`

Dedupe is simply: `article_id` already in `articles` (the PK). No `served_articles` table, and no `served` boolean column — existence *is* the flag.

```text
RSS entry (new link)
    → INSERT articles          -- immediate
    → INSERT sentiments*       -- after LLM
    → INSERT buy_orders*       -- if positive + tradable
    → INSERT sell_orders*      -- after hold
```

For crash recovery after insert-but-before-analysis, use a nullable timestamp on `articles` (e.g. `sentiment_analyzed_at`) rather than a parallel served set: `WHERE sentiment_analyzed_at IS NULL` finds work to resume.

---

## Buy vs sell: two tables

**Use separate `buy_orders` and `sell_orders` tables.**

TrendLine’s domain is not a generic order blotter — it is a fixed lifecycle: buy on positive sentiment → hold → sell that specific buy. That maps cleanly to two tables with a 1:1 FK:

```text
buy_orders (1) ──── (0..1) sell_orders
                 UNIQUE(buy_order_id) on sell_orders
```

Why separate wins here:

- **Clearer constraints.** Sell always has a `buy_order_id NOT NULL`; buy never has a self-FK. No `side` CHECK gymnastics.
- **Cleaner queries for this app.** Ready-to-sell is “filled buys with no sell yet (or buy not terminal) past hold time,” not a filtered slice of a mixed table.
- **Matches the existing mental model** (`buy_orders` / `sell_orders` dicts in [`TradeLifecycleManager`](../src/trade_lifecycle_manager.py)).
- **Slightly different lifecycle flags** (`buy_order_terminal` vs `sell_order_terminal`) live naturally on each table.

A single `orders` table is better for broker-style apps that list every order together or support many order types. TrendLine does not need that.

---

## Entity relationship overview

```mermaid
erDiagram
    news_sources ||--o{ articles : publishes
    articles ||--o{ sentiments : has
    sentiments ||--o| buy_orders : triggers
    buy_orders ||--o| sell_orders : closed_by

    news_sources {
        text name PK
        text url
    }
    articles {
        text article_id PK
        text source_name FK
        text title
        timestamptz archived_at
        timestamptz sentiment_analyzed_at
        boolean resulted_in_purchase
    }
    sentiments {
        bigserial id PK
        text article_id FK
        text company
        text ticker
        text sentiment
    }
    buy_orders {
        uuid alpaca_order_id PK
        bigint sentiment_id FK
        text article_id FK
        text symbol
        boolean is_terminal
    }
    sell_orders {
        uuid alpaca_order_id PK
        uuid buy_order_id FK_UK
        boolean is_terminal
    }
```

---

## Proposed tables

### 1. `news_sources`

Replaces the `rss_feeds` dict in the news snapshot / [`RSS_FEED_URLS`](../src/configs.py).

| Column | Type | Notes |
|--------|------|-------|
| `name` | `TEXT PRIMARY KEY` | e.g. `NPR`, `CNBC` |
| `url` | `TEXT NOT NULL` | Feed URL |
| `is_active` | `BOOLEAN NOT NULL DEFAULT TRUE` | Soft-disable a feed |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Seed from current `RSS_FEED_URLS`.

---

### 2. `articles`

One row per discovered headline. Inserted as soon as the scraper sees a new link; that row is also the dedupe record (replaces `served_articles`).

| Column | Type | Notes |
|--------|------|-------|
| `article_id` | `TEXT PRIMARY KEY` | RSS `link` (same as today) |
| `source_name` | `TEXT NOT NULL REFERENCES news_sources(name)` | |
| `title` | `TEXT` | From `article_entry.title` (nullable if empty at discovery) |
| `summary` | `TEXT` | From `article_entry.summary` |
| `published_at` | `TIMESTAMPTZ` | Parsed from RSS `published` / `published_parsed` when possible |
| `published_raw` | `TEXT` | Original RFC822 string |
| `rss_guid` | `TEXT` | Feed `id` when present (may differ from link) |
| `raw_entry` | `JSONB NOT NULL` | Full feedparser entry as JSON (replaces pickled `FeedParserDict`) |
| `archived_at` | `TIMESTAMPTZ NOT NULL` | UTC discovery/insert time |
| `sentiment_analyzed_at` | `TIMESTAMPTZ` | Null until LLM step completes (or is skipped); resume query target |
| `resulted_in_purchase` | `BOOLEAN NOT NULL DEFAULT FALSE` | True if any buy_orders exist for this article |
| `sentiment_raw_response` | `TEXT` | Full LLM output for the article-level analysis call |
| `sentiment_format_match` | `BOOLEAN` | Whether the LLM response matched expected format |

LLM call metadata stays on the article (one analysis call per headline today). Per-company outcomes live in `sentiments`.

**Indexes:** `(source_name)`, `(archived_at DESC)`, `(resulted_in_purchase)` where true, `(sentiment_analyzed_at)` where null (pending analysis).

---

### 3. `sentiments` (1 article → many sentiments)

One row per company/ticker mentioned for an article — **not** 1:1 with articles.

Today’s pickled [`SentimentResponse`](../src/base/sentiment_response.py) stores one sentiment string plus a comma-joined `ticker` field. In the relational model that expands: e.g. `ticker="NVDA,GLW"`, `sentiment="positive"` becomes two rows sharing the same sentiment value (until the LLM is changed to emit per-company scores).

| Column | Type | Notes |
|--------|------|-------|
| `id` | `BIGSERIAL PRIMARY KEY` | Surrogate key; buy orders can FK here |
| `article_id` | `TEXT NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE` | |
| `company` | `TEXT` | Company name (from `TickerService` / Alpaca asset name, or LLM later) |
| `ticker` | `TEXT NOT NULL` | Uppercase symbol |
| `sentiment` | `TEXT NOT NULL` | `positive` / `neutral` / `negative` / `NONE` / `''` |
| `ticker_validated` | `BOOLEAN NOT NULL DEFAULT FALSE` | This ticker passed Alpaca tradable check (`ticker_found` split per symbol) |
| `ordinal` | `SMALLINT NOT NULL DEFAULT 0` | Preserve mention order from LLM list |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

**Constraints / indexes:**

- `UNIQUE (article_id, ticker)`
- Index on `(ticker)`, `(sentiment)`, `(article_id)`

Articles with no extractable tickers get **zero** sentiment rows (dashboard can still show the article via `articles` alone). That replaces today’s “one null-ticker dataframe row” pattern.

`article_tickers` is **dropped** — `sentiments` is the ticker association table.

---

### 4. `buy_orders`

| Column | Type | Notes |
|--------|------|-------|
| `alpaca_order_id` | `UUID PRIMARY KEY` | Alpaca `Order.id` |
| `client_order_id` | `TEXT` | |
| `article_id` | `TEXT NOT NULL REFERENCES articles(article_id)` | Denormalized for simple article queries |
| `sentiment_id` | `BIGINT REFERENCES sentiments(id)` | The positive sentiment row that triggered the buy |
| `symbol` | `TEXT NOT NULL` | Should match `sentiments.ticker` when `sentiment_id` set |
| `qty` | `NUMERIC` | |
| `filled_qty` | `NUMERIC` | |
| `filled_avg_price` | `NUMERIC` | |
| `status` | `TEXT NOT NULL` | Alpaca status string |
| `order_type` | `TEXT` | e.g. `market` |
| `time_in_force` | `TEXT` | e.g. `gtc` |
| `submitted_at` | `TIMESTAMPTZ` | |
| `created_at` | `TIMESTAMPTZ` | Broker timestamps |
| `updated_at` | `TIMESTAMPTZ` | |
| `filled_at` | `TIMESTAMPTZ` | Critical for hold-time / ready-to-sell |
| `is_terminal` | `BOOLEAN NOT NULL DEFAULT FALSE` | Was `buy_order_terminal[symbol]` |
| `raw_order` | `JSONB` | Full Alpaca order dump |

**Indexes:** `(article_id, symbol)`, `(filled_at)` where `NOT is_terminal AND status = 'filled'`, `(sentiment_id)`.

**Ready-to-sell** (replaces pickled `ready_to_sell` list):

```sql
SELECT b.*
FROM buy_orders b
LEFT JOIN sell_orders s ON s.buy_order_id = b.alpaca_order_id
WHERE s.buy_order_id IS NULL
  AND NOT b.is_terminal
  AND b.status = 'filled'
  AND b.filled_at IS NOT NULL
  AND b.filled_at <= now() - interval '4 hours';  -- MARKET_HOLD_TIME
```

---

### 5. `sell_orders`

| Column | Type | Notes |
|--------|------|-------|
| `alpaca_order_id` | `UUID PRIMARY KEY` | Alpaca `Order.id` |
| `buy_order_id` | `UUID NOT NULL UNIQUE REFERENCES buy_orders(alpaca_order_id)` | Enforces **1:1** with buy |
| `symbol` | `TEXT NOT NULL` | Redundant with buy but handy; should match buy.symbol |
| `qty` | `NUMERIC` | |
| `filled_qty` | `NUMERIC` | |
| `filled_avg_price` | `NUMERIC` | |
| `status` | `TEXT NOT NULL` | |
| `order_type` | `TEXT` | |
| `time_in_force` | `TEXT` | |
| `submitted_at` | `TIMESTAMPTZ` | |
| `created_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | |
| `filled_at` | `TIMESTAMPTZ` | |
| `is_terminal` | `BOOLEAN NOT NULL DEFAULT FALSE` | Was `sell_order_terminal[symbol]` |
| `raw_order` | `JSONB` | |

No separate `article_id` required (reachable via buy → article), but adding `article_id` is fine if you want flatter dashboard queries.

---

## What deliberately disappears

| Current construct | Relational replacement |
|-------------------|------------------------|
| `_article_id_index` | Primary key on `articles` |
| `_buy_order_id_index` | PK on `buy_orders` + `article_id` FK |
| `ready_to_sell` list | Query on `buy_orders` anti-joined to `sell_orders` |
| `served_articles` set | Existence of row in `articles` (insert at discovery) |
| `news_data` etag/modified / last feed | In-memory only for the process lifetime |
| Pickled Alpaca `Order` objects | Projected columns + `raw_order` JSONB on buy/sell tables |
| Pickled `FeedParserDict` | Projected columns + `raw_entry` JSONB |
| Pickled `SentimentResponse` (1 blob / article) | `articles.sentiment_*` metadata + many `sentiments` rows |
| Separate `article_tickers` table | Folded into `sentiments` |
| `feed_http_state` table | Not used — etag/modified stay in memory |

---

## Dashboard / analytics mapping

[`to_dataframe`](../src/trade_lifecycle_manager.py) becomes roughly:

```text
articles
  LEFT JOIN sentiments ON sentiments.article_id = articles.article_id
  LEFT JOIN buy_orders ON buy_orders.sentiment_id = sentiments.id
  LEFT JOIN sell_orders ON sell_orders.buy_order_id = buy_orders.alpaca_order_id
```

One UI row per sentiment (company/ticker). Articles with no sentiments appear once via a separate query or `LEFT JOIN` with null ticker columns.

Derived PnL (`invested`, `proceeds`, `pnl`) stays computed in Python or as a SQL view — do not store it.

---

## Suggested DDL sketch

```sql
CREATE TABLE news_sources (
  name TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE articles (
  article_id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL REFERENCES news_sources(name),
  title TEXT,
  summary TEXT,
  published_at TIMESTAMPTZ,
  published_raw TEXT,
  rss_guid TEXT,
  raw_entry JSONB NOT NULL,
  archived_at TIMESTAMPTZ NOT NULL,
  sentiment_analyzed_at TIMESTAMPTZ,
  resulted_in_purchase BOOLEAN NOT NULL DEFAULT FALSE,
  sentiment_raw_response TEXT,
  sentiment_format_match BOOLEAN
);
CREATE INDEX idx_articles_source ON articles(source_name);
CREATE INDEX idx_articles_archived_at ON articles(archived_at DESC);
CREATE INDEX idx_articles_pending_sentiment
  ON articles(archived_at)
  WHERE sentiment_analyzed_at IS NULL;

CREATE TABLE sentiments (
  id BIGSERIAL PRIMARY KEY,
  article_id TEXT NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
  company TEXT,
  ticker TEXT NOT NULL,
  sentiment TEXT NOT NULL,
  ticker_validated BOOLEAN NOT NULL DEFAULT FALSE,
  ordinal SMALLINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (article_id, ticker)
);
CREATE INDEX idx_sentiments_ticker ON sentiments(ticker);
CREATE INDEX idx_sentiments_sentiment ON sentiments(sentiment);

CREATE TABLE buy_orders (
  alpaca_order_id UUID PRIMARY KEY,
  client_order_id TEXT,
  article_id TEXT NOT NULL REFERENCES articles(article_id),
  sentiment_id BIGINT REFERENCES sentiments(id),
  symbol TEXT NOT NULL,
  qty NUMERIC,
  filled_qty NUMERIC,
  filled_avg_price NUMERIC,
  status TEXT NOT NULL,
  order_type TEXT,
  time_in_force TEXT,
  submitted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  filled_at TIMESTAMPTZ,
  is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
  raw_order JSONB
);
CREATE INDEX idx_buy_orders_article_symbol ON buy_orders(article_id, symbol);
CREATE INDEX idx_buy_orders_ready_to_sell
  ON buy_orders(filled_at)
  WHERE NOT is_terminal AND status = 'filled';

CREATE TABLE sell_orders (
  alpaca_order_id UUID PRIMARY KEY,
  buy_order_id UUID NOT NULL UNIQUE REFERENCES buy_orders(alpaca_order_id),
  symbol TEXT NOT NULL,
  qty NUMERIC,
  filled_qty NUMERIC,
  filled_avg_price NUMERIC,
  status TEXT NOT NULL,
  order_type TEXT,
  time_in_force TEXT,
  submitted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  filled_at TIMESTAMPTZ,
  is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
  raw_order JSONB
);
```

---

## Migration notes (schema-informed, not implementing yet)

When expanding today’s `SentimentResponse`:

1. Split `ticker` on commas → one `sentiments` row per symbol.
2. Copy the single `sentiment` value onto each row (current LLM behavior).
3. Resolve `company` via `TickerService` / Alpaca asset name at migration time when possible.
4. Set `ticker_validated` from whether that symbol was in the validated tradable set (or `True` if `ticker_found` and symbol appears in buys / validated list).
5. Store `raw_response` / `format_match` on `articles`; set `sentiment_analyzed_at` from `archived_at` for migrated rows that already have analysis.
6. Union of snapshot `served_articles` and archived `article_id`s → `articles` rows (served-only IDs become article stubs if raw RSS is unavailable, or are dropped if you only care about archived history).

Buy/sell dicts migrate row-for-row into `buy_orders` / `sell_orders`, linking `sentiment_id` by `(article_id, symbol)`.

---

## Design choices locked in

- **Database engine: PostgreSQL.** JSONB for raw RSS/order blobs; project only fields the loop and dashboard actually use.
- **Python stack: plain SQL + psycopg3.** DDL in `.sql` files; no ORM.
- **Insert `articles` at RSS discovery**; dedupe via PK — no `served_articles` table or `served` column.
- **`sentiment_analyzed_at`** marks completed (or skipped) analysis so a crash mid-loop can resume.
- **1 article → many `sentiments`** (company + ticker + sentiment per row); no separate `article_tickers` table.
- **Separate `buy_orders` and `sell_orders`** with `sell_orders.buy_order_id UNIQUE` for the 1:1 close relationship.
- **No table for ready-to-sell, timing, Alpaca portfolio, or feed HTTP cache** — query, live API, or in-memory.
- **RSS etag/modified stay in memory** while the process runs; not persisted.
- **LLM call metadata on `articles`**; per-company outcomes in `sentiments`.
