-- Phase 1 storage model.
--
-- One table for all instruments, ORDER BY (instrument_id, event_time).
-- The previous version of this project created a table per symbol
-- (AAPL, AAPL_historical, AAPL_tick, ...) and then needed ALLOW FILTERING on
-- every read, which is a full scan wearing a WHERE clause.

CREATE DATABASE IF NOT EXISTS market;

-- Landing table: the trade stream, one row per execution.
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

-- Kafka engine table. Decodes the topic using the committed proto contract
-- mounted at /var/lib/clickhouse/format_schemas.
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
    kafka_group_name  = 'clickhouse-ticks-v1',
    kafka_format      = 'ProtobufSingle',
    kafka_schema      = 'market/v1/tick.proto:Tick',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream';

-- Pump: casts the wire's epoch-microsecond integers into real timestamps.
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
    now()      AS occurred_at,
    _topic     AS topic,
    _partition AS partition,
    _offset    AS offset,
    _raw_message AS raw,
    _error     AS error
FROM market.ticks_queue
WHERE length(_error) > 0;

-- Phase 1 serves bars by aggregating ticks on read. Phase 2 replaces this view
-- with a Flink-computed `market.bars` table, where the window boundaries are
-- defined by event-time watermarks rather than by whatever happens to have
-- arrived when the query runs.
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
