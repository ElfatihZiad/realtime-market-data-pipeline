-- Storage: the tables dbt reads and the streaming pipeline writes.
--
-- Deliberately separate from 02-streaming.sql. Everything here is plain
-- MergeTree and needs nothing but ClickHouse, so CI can create it and run
-- `dbt build` against a bare server. The Kafka engine tables and their
-- materialised views live next door, because they need a broker and a schema
-- registry to exist.
--
-- One table per concept for all instruments, ORDER BY (instrument_id, time).
-- The previous version of this project created a table per symbol
-- (AAPL, AAPL_historical, AAPL_tick, ...) and then needed ALLOW FILTERING on
-- every read, which is a full scan wearing a WHERE clause.

-- Storage model.
--
-- One table per concept for all instruments, ORDER BY (instrument_id, time).
-- The previous version of this project created a table per symbol
-- (AAPL, AAPL_historical, AAPL_tick, ...) and then needed ALLOW FILTERING on
-- every read, which is a full scan wearing a WHERE clause.
--
-- Every Kafka engine table below decodes Avro via the schema registry
-- (AvroConfluent), so the registry is the one place a contract lives.

CREATE DATABASE IF NOT EXISTS market;

-- ─────────────────────────────── ticks ───────────────────────────────

CREATE TABLE IF NOT EXISTS market.ticks
(
    instrument_id  LowCardinality(String),
    venue          LowCardinality(String),
    event_time     DateTime64(6, 'UTC'),
    ingest_time    DateTime64(6, 'UTC'),
    price          Float64,
    size           Float64,
    side           LowCardinality(String),
    sequence       String,
    -- ingest_time - event_time: end-to-end pipeline latency, per tick.
    latency_us     Int64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (instrument_id, event_time);

-- Rows the Kafka engine could not decode, kept rather than dropped.
CREATE TABLE IF NOT EXISTS market.ticks_errors
(
    occurred_at DateTime DEFAULT now(),
    topic       String,
    partition   UInt64,
    offset      UInt64,
    raw         String,
    error       String
)
ENGINE = MergeTree
ORDER BY occurred_at;

-- ──────────────────────────────── bars ────────────────────────────────
-- Produced by Flink over event-time tumbling windows. A bar lands here when
-- the watermark passed its window end, not when wall clock did.

CREATE TABLE IF NOT EXISTS market.bars
(
    instrument_id  LowCardinality(String),
    bar_interval   LowCardinality(String),
    window_start   DateTime64(3, 'UTC'),
    window_end     DateTime64(3, 'UTC'),
    open           Float64,
    high           Float64,
    low            Float64,
    close          Float64,
    volume         Float64,
    vwap           Float64,
    trades         UInt64
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(window_start)
ORDER BY (instrument_id, bar_interval, window_start);

-- ──────────────────────────── late arrivals ────────────────────────────
-- Trades that arrived after the watermark had already closed their window.
-- They are NOT silently dropped and they do NOT retroactively mutate a bar
-- that downstream consumers have already seen; they are recorded here so the
-- cost of the watermark delay is measurable.

CREATE TABLE IF NOT EXISTS market.ticks_late
(
    instrument_id  LowCardinality(String),
    venue          LowCardinality(String),
    event_time     DateTime64(6, 'UTC'),
    ingest_time    DateTime64(6, 'UTC'),
    price          Float64,
    size           Float64,
    side           LowCardinality(String),
    sequence       String,
    -- how far past the watermark this trade was when it showed up
    lateness_ms    Int64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (instrument_id, event_time);

-- ─────────────────────────────── signals ───────────────────────────────
-- Realized volatility and spike detection over the bar stream.

CREATE TABLE IF NOT EXISTS market.signals
(
    instrument_id  LowCardinality(String),
    bar_end        DateTime64(3, 'UTC'),
    close          Float64,
    log_return     Nullable(Float64),
    realized_vol   Nullable(Float64),
    zscore         Nullable(Float64),
    is_spike       Bool
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(bar_end)
ORDER BY (instrument_id, bar_end);

-- Kept from Phase 1 for comparison: bars aggregated from raw trades on READ,
-- with no notion of event time or completeness. Useful as the reference the
-- Flink output is checked against, and as the thing it improves on.
CREATE VIEW IF NOT EXISTS market.bars_1m_live AS
SELECT
    instrument_id,
    toStartOfMinute(event_time)                   AS bucket,
    argMin(price, event_time)                     AS open,
    max(price)                                    AS high,
    min(price)                                    AS low,
    argMax(price, event_time)                     AS close,
    sum(size)                                     AS volume,
    sum(price * size) / nullIf(sum(size), 0)      AS vwap,
    count()                                       AS trades
FROM market.ticks
GROUP BY instrument_id, bucket;

-- ───────────────────────────── news & sentiment ─────────────────────────────

CREATE TABLE IF NOT EXISTS market.news
(
    article_id     String,
    instrument_id  LowCardinality(String),
    source         LowCardinality(String),
    title          String,
    url            String,
    published_at   DateTime64(3, 'UTC'),
    ingest_time    DateTime64(3, 'UTC'),
    sentiment      Float64,
    scorer         LowCardinality(String)
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(published_at)
ORDER BY (instrument_id, published_at, article_id);

-- The windowed join of news sentiment against price, computed by Flink.
-- Rows exist only for windows that had BOTH trades and news.
CREATE TABLE IF NOT EXISTS market.sentiment
(
    instrument_id  LowCardinality(String),
    window_start   DateTime64(3, 'UTC'),
    window_end     DateTime64(3, 'UTC'),
    articles       UInt64,
    avg_sentiment  Float64,
    min_sentiment  Float64,
    max_sentiment  Float64,
    open           Float64,
    close          Float64,
    return_pct     Float64,
    volume         Float64,
    trades         UInt64
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(window_start)
ORDER BY (instrument_id, window_start);
