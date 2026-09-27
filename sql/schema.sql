


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

CREATE TABLE orders (
  alpaca_order_id   UUID PRIMARY KEY,
  side              TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
  symbol            TEXT NOT NULL,
  status            TEXT NOT NULL,

  client_order_id   TEXT,
  asset_id          UUID,
  asset_class       TEXT,
  order_class       TEXT,
  order_type        TEXT,
  type              TEXT,
  time_in_force     TEXT,
  position_intent   TEXT,

  qty               NUMERIC,
  notional          NUMERIC,
  filled_qty        NUMERIC,
  filled_avg_price  NUMERIC,
  limit_price       NUMERIC,
  stop_price        NUMERIC,
  trail_percent     NUMERIC,
  trail_price       NUMERIC,
  hwm               NUMERIC,
  ratio_qty         NUMERIC,
  extended_hours    BOOLEAN,

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

  legs              JSONB,
  raw               JSONB NOT NULL,

  is_terminal       BOOLEAN GENERATED ALWAYS AS
  (status IN ('filled', 'canceled', 'expired', 'rejected')) STORED
);
CREATE INDEX idx_orders_open ON orders (alpaca_order_id) WHERE NOT is_terminal;
CREATE INDEX idx_orders_symbol ON orders (symbol);

CREATE TABLE trades (
  id                  BIGSERIAL PRIMARY KEY,
  sentiment_id        BIGINT NOT NULL UNIQUE REFERENCES sentiments(id),
  article_id          TEXT   NOT NULL REFERENCES articles(article_id),
  symbol              TEXT   NOT NULL,

  buy_attempted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  buy_order_id        UUID UNIQUE REFERENCES orders(alpaca_order_id),
  buy_failure_reason  TEXT,

  sell_attempted_at   TIMESTAMPTZ,
  sell_order_id       UUID UNIQUE REFERENCES orders(alpaca_order_id),
  sell_failure_reason TEXT,

  CHECK ((buy_order_id IS NULL) <> (buy_failure_reason IS NULL)),
  CHECK (NOT (sell_order_id IS NOT NULL AND sell_failure_reason IS NOT NULL))
);
CREATE INDEX idx_trades_article ON trades (article_id);
CREATE INDEX idx_trades_buy_order ON trades (buy_order_id);
CREATE INDEX idx_trades_sell_order ON trades (sell_order_id);


CREATE TABLE heartbeat (
  id               INT PRIMARY KEY,  -- always 1
  last_seen        TIMESTAMPTZ NOT NULL
);

INSERT INTO heartbeat (id, last_seen) VALUES (1, now())
ON CONFLICT (id) DO NOTHING;

CREATE TABLE logs(
  created_at      TIMESTAMPTZ NOT NULL,
  level           TEXT NOT NULL,
  message         TEXT NOT NULL
);

CREATE INDEX idx_logs_created_at ON logs (created_at DESC);