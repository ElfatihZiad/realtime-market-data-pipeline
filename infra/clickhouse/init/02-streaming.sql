-- Ingestion: Kafka engine tables and the materialised views that pump them
-- into the MergeTree tables in 01-tables.sql.
--
-- These need a reachable broker and schema registry, which is why they are not
-- in the file CI applies. Every one decodes Avro through the registry, so the
-- registry is the single place a contract lives.

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
