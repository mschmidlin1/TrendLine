-- 1. news_sources
-- 2. articles        → references news_sources
-- 3. sentiments      → references articles
-- 4. buy_orders      → references articles + sentiments
-- 5. sell_orders     → references buy_orders


CREATE TABLE news_sources (
  id         BIGSERIAL PRIMARY KEY,   -- DB generates 1, 2, 3, ...
  name       TEXT NOT NULL,           -- "CNBC" — NOT unique
  url        TEXT NOT NULL UNIQUE,    -- one row per feed URL
  is_active  BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE articles (
  article_id              TEXT PRIMARY KEY,  -- RSS link URL
  source_id               BIGINT NOT NULL REFERENCES news_sources(id),
  title                   TEXT,
  summary                 TEXT,
  published_at            TIMESTAMPTZ,
  published_raw           TEXT,
  rss_guid                TEXT,
  raw_entry               JSONB NOT NULL,
  archived_at             TIMESTAMPTZ NOT NULL,  -- discovery/insert time (you set this in Python)
  sentiment_analyzed_at   TIMESTAMPTZ,           -- NULL until analysis done/skipped
  resulted_in_purchase    BOOLEAN NOT NULL DEFAULT FALSE,
  sentiment_raw_response  TEXT,
  sentiment_format_match  BOOLEAN
);

CREATE INDEX idx_articles_source ON articles(source_id);
CREATE INDEX idx_articles_archived_at ON articles(archived_at DESC);
CREATE INDEX idx_articles_pending_sentiment
  ON articles(archived_at)
  WHERE sentiment_analyzed_at IS NULL;


CREATE TABLE sentiments (
  id                BIGSERIAL PRIMARY KEY,
  article_id        TEXT NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
  company           TEXT,
  ticker            TEXT NOT NULL,
  sentiment         TEXT NOT NULL,  -- positive / neutral / negative / NONE / ''
  ticker_valid      BOOLEAN NOT NULL DEFAULT FALSE,
  ordinal           SMALLINT NOT NULL DEFAULT 0,  -- order from LLM ticker list
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (article_id, ticker)
);

CREATE INDEX idx_sentiments_ticker ON sentiments(ticker);
CREATE INDEX idx_sentiments_sentiment ON sentiments(sentiment);


CREATE TABLE buy_orders (
  -- TrendLine linkage
  article_id        TEXT NOT NULL REFERENCES articles(article_id),
  sentiment_id      BIGINT REFERENCES sentiments(id),
  is_terminal       BOOLEAN NOT NULL DEFAULT FALSE,

  -- Alpaca Order fields
  alpaca_order_id   UUID PRIMARY KEY,              -- Order.id
  client_order_id   TEXT,
  created_at        TIMESTAMPTZ,
  updated_at        TIMESTAMPTZ,
  submitted_at      TIMESTAMPTZ,
  filled_at         TIMESTAMPTZ,
  expired_at        TIMESTAMPTZ,
  expires_at        TIMESTAMPTZ,
  canceled_at       TIMESTAMPTZ,
  failed_at         TIMESTAMPTZ,
  replaced_at       TIMESTAMPTZ,
  replaced_by       UUID,
  replaces          UUID,
  asset_id          UUID,
  symbol            TEXT NOT NULL,
  asset_class       TEXT,
  notional          NUMERIC,
  qty               NUMERIC,
  filled_qty        NUMERIC,
  filled_avg_price  NUMERIC,
  order_class       TEXT,
  order_type        TEXT,
  type              TEXT,                          -- Alpaca also exposes Order.type
  side              TEXT,
  time_in_force     TEXT,
  limit_price       NUMERIC,
  stop_price        NUMERIC,
  status            TEXT NOT NULL,
  extended_hours    BOOLEAN,
  legs              JSONB,                         -- nested list of Order, if any
  trail_percent     NUMERIC,
  trail_price       NUMERIC,
  hwm               NUMERIC,
  position_intent   TEXT,
  ratio_qty         NUMERIC
);

CREATE INDEX idx_buy_orders_article_symbol ON buy_orders(article_id, symbol);
CREATE INDEX idx_buy_orders_sentiment ON buy_orders(sentiment_id);
CREATE INDEX idx_buy_orders_ready_to_sell
  ON buy_orders(filled_at)
  WHERE NOT is_terminal AND status = 'filled';


CREATE TABLE sell_orders (
  -- TrendLine linkage
  buy_order_id      UUID NOT NULL UNIQUE REFERENCES buy_orders(alpaca_order_id),
  is_terminal       BOOLEAN NOT NULL DEFAULT FALSE,

  -- Alpaca Order fields (same shape as buy_orders)
  alpaca_order_id   UUID PRIMARY KEY,              -- Order.id
  client_order_id   TEXT,
  created_at        TIMESTAMPTZ,
  updated_at        TIMESTAMPTZ,
  submitted_at      TIMESTAMPTZ,
  filled_at         TIMESTAMPTZ,
  expired_at        TIMESTAMPTZ,
  expires_at        TIMESTAMPTZ,
  canceled_at       TIMESTAMPTZ,
  failed_at         TIMESTAMPTZ,
  replaced_at       TIMESTAMPTZ,
  replaced_by       UUID,
  replaces          UUID,
  asset_id          UUID,
  symbol            TEXT NOT NULL,
  asset_class       TEXT,
  notional          NUMERIC,
  qty               NUMERIC,
  filled_qty        NUMERIC,
  filled_avg_price  NUMERIC,
  order_class       TEXT,
  order_type        TEXT,
  type              TEXT,
  side              TEXT,
  time_in_force     TEXT,
  limit_price       NUMERIC,
  stop_price        NUMERIC,
  status            TEXT NOT NULL,
  extended_hours    BOOLEAN,
  legs              JSONB,
  trail_percent     NUMERIC,
  trail_price       NUMERIC,
  hwm               NUMERIC,
  position_intent   TEXT,
  ratio_qty         NUMERIC
);

CREATE INDEX idx_sell_orders_symbol ON sell_orders(symbol);
CREATE INDEX idx_sell_orders_open
  ON sell_orders(submitted_at)
  WHERE NOT is_terminal;
