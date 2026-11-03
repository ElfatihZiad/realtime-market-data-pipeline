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

CREATE TABLE IF NOT EXISTS market.ticks_queue
(
    instrument_id  String,
    venue          String,
    event_time_us  Int64,
    ingest_time_us Int64,
    price          Float64,
    size           Float64,
    side           String,
    sequence       String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list  = 'ticks.raw',
    kafka_group_name  = 'clickhouse-ticks-v2',
    kafka_format      = 'AvroConfluent',
    format_avro_schema_registry_url = 'http://schema-registry:8081',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream';

CREATE MATERIALIZED VIEW IF NOT EXISTS market.ticks_mv TO market.ticks AS
SELECT
    instrument_id,
    venue,
    fromUnixTimestamp64Micro(event_time_us, 'UTC')  AS event_time,
    fromUnixTimestamp64Micro(ingest_time_us, 'UTC') AS ingest_time,
    price,
    size,
    side,
    sequence,
    ingest_time_us - event_time_us                  AS latency_us
FROM market.ticks_queue
WHERE length(_error) = 0;

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

CREATE MATERIALIZED VIEW IF NOT EXISTS market.ticks_errors_mv TO market.ticks_errors AS
SELECT
    now()        AS occurred_at,
    _topic       AS topic,
    _partition   AS partition,
    _offset      AS offset,
    _raw_message AS raw,
    _error       AS error
FROM market.ticks_queue
WHERE length(_error) > 0;

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

CREATE TABLE IF NOT EXISTS market.bars_queue
(
    instrument_id   String,
    bar_interval    String,
    window_start_ms Int64,
    window_end_ms   Int64,
    open            Float64,
    high            Float64,
    low             Float64,
    close           Float64,
    volume          Float64,
    vwap            Float64,
    trades          Int64
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list  = 'bars.1m,bars.5m',
    kafka_group_name  = 'clickhouse-bars-v1',
    kafka_format      = 'AvroConfluent',
    format_avro_schema_registry_url = 'http://schema-registry:8081',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream';

CREATE MATERIALIZED VIEW IF NOT EXISTS market.bars_mv TO market.bars AS
SELECT
    instrument_id,
    bar_interval,
    fromUnixTimestamp64Milli(window_start_ms, 'UTC') AS window_start,
    fromUnixTimestamp64Milli(window_end_ms, 'UTC')   AS window_end,
    open, high, low, close, volume, vwap,
    toUInt64(trades)                                 AS trades
FROM market.bars_queue
WHERE length(_error) = 0;

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

CREATE TABLE IF NOT EXISTS market.ticks_late_queue
(
    instrument_id  String,
    venue          String,
    event_time_us  Int64,
    ingest_time_us Int64,
    price          Float64,
    size           Float64,
    side           String,
    sequence       String,
    lateness_ms    Int64
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list  = 'ticks.late',
    kafka_group_name  = 'clickhouse-ticks-late-v1',
    kafka_format      = 'AvroConfluent',
    format_avro_schema_registry_url = 'http://schema-registry:8081',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream';

CREATE MATERIALIZED VIEW IF NOT EXISTS market.ticks_late_mv TO market.ticks_late AS
SELECT
    instrument_id,
    venue,
    fromUnixTimestamp64Micro(event_time_us, 'UTC')  AS event_time,
    fromUnixTimestamp64Micro(ingest_time_us, 'UTC') AS ingest_time,
    price, size, side, sequence, lateness_ms
FROM market.ticks_late_queue
WHERE length(_error) = 0;

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

CREATE TABLE IF NOT EXISTS market.signals_queue
(
    instrument_id  String,
    bar_end_ms     Int64,
    close          Float64,
    log_return     Nullable(Float64),
    realized_vol   Nullable(Float64),
    zscore         Nullable(Float64),
    is_spike       Bool
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list  = 'signals.1m',
    kafka_group_name  = 'clickhouse-signals-v1',
    kafka_format      = 'AvroConfluent',
    format_avro_schema_registry_url = 'http://schema-registry:8081',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream';

CREATE MATERIALIZED VIEW IF NOT EXISTS market.signals_mv TO market.signals AS
SELECT
    instrument_id,
    fromUnixTimestamp64Milli(bar_end_ms, 'UTC') AS bar_end,
    close, log_return, realized_vol, zscore, is_spike
FROM market.signals_queue
WHERE length(_error) = 0;

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
