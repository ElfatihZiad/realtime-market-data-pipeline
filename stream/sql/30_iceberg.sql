-- ───────────────────────────────────────────────────────────────────────────
-- Lake sink: the same streams, landed as Iceberg tables.
--
-- ClickHouse is the hot store — it answers dashboard queries in milliseconds
-- but keeps data on local disk and is not where you want five years of ticks.
-- Iceberg is the history: open Parquet files any engine can read, with
-- snapshots, schema evolution and time travel.
--
-- Both are written from the same stream rather than one being derived from the
-- other, so neither is the other's cache and a failure in one does not corrupt
-- the other.
--
-- The Iceberg sink commits on CHECKPOINT, not per record. With
-- execution.checkpointing.interval at 10s, a row appears in the table within
-- ~10s of being processed, and each commit is one atomic Iceberg snapshot.
-- ───────────────────────────────────────────────────────────────────────────

SET 'pipeline.name' = 'mdp-iceberg';
SET 'table.local-time-zone' = 'UTC';
SET 'execution.runtime-mode' = 'streaming';
SET 'table.exec.source.idle-timeout' = '10s';

CREATE CATALOG iceberg WITH (
    'type' = 'iceberg',
    'catalog-type' = 'rest',
    'uri' = 'http://iceberg-rest:8181',
    'warehouse' = 's3://warehouse/',
    -- Iceberg writes through S3FileIO (the AWS SDK), so nothing here touches
    -- Hadoop's local filesystem. Point these at real S3 and the job is unchanged.
    's3.endpoint' = 'http://s3mock:9090',
    's3.path-style-access' = 'true',
    's3.access-key-id' = 'mdp',
    's3.secret-access-key' = 'mdp-secret',
    'client.region' = 'us-east-1'
);

CREATE DATABASE IF NOT EXISTS iceberg.market;

-- Partitioned by date first, then instrument: almost every query over history
-- is "this instrument, this period", and date-first pruning is what keeps a
-- five-year scan from reading five years of files.
CREATE TABLE IF NOT EXISTS iceberg.market.ticks (
    dt              DATE,
    instrument_id   STRING,
    venue           STRING,
    event_time      TIMESTAMP(3),
    ingest_time     TIMESTAMP(3),
    price           DOUBLE,
    `size`          DOUBLE,
    side            STRING,
    `sequence`      STRING,
    latency_us      BIGINT
) PARTITIONED BY (dt, instrument_id);

CREATE TABLE IF NOT EXISTS iceberg.market.bars (
    dt              DATE,
    instrument_id   STRING,
    bar_interval    STRING,
    window_start    TIMESTAMP(3),
    window_end      TIMESTAMP(3),
    `open`          DOUBLE,
    high            DOUBLE,
    low             DOUBLE,
    `close`         DOUBLE,
    volume          DOUBLE,
    vwap            DOUBLE,
    trades          BIGINT
) PARTITIONED BY (dt, instrument_id);

-- Sources. Both start at the earliest retained offset so the lake picks up
-- everything Kafka still holds, rather than only what arrives from now on.
CREATE TABLE ticks_src (
    instrument_id   STRING,
    venue           STRING,
    event_time_us   BIGINT,
    ingest_time_us  BIGINT,
    price           DOUBLE,
    `size`          DOUBLE,
    side            STRING,
    `sequence`      STRING
) WITH (
    'connector' = 'kafka',
    'topic' = 'ticks.raw',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-iceberg-ticks-v1',
    'scan.startup.mode' = 'earliest-offset',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081'
);

CREATE TABLE bars_src (
    instrument_id    STRING,
    bar_interval     STRING,
    window_start_ms  BIGINT,
    window_end_ms    BIGINT,
    `open`           DOUBLE,
    high             DOUBLE,
    low              DOUBLE,
    `close`          DOUBLE,
    volume           DOUBLE,
    vwap             DOUBLE,
    trades           BIGINT
) WITH (
    'connector' = 'kafka',
    'topic' = 'bars.1m;bars.5m',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-iceberg-bars-v1',
    'scan.startup.mode' = 'earliest-offset',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081'
);

EXECUTE STATEMENT SET
BEGIN

INSERT INTO iceberg.market.ticks
SELECT
    CAST(TO_TIMESTAMP_LTZ(event_time_us / 1000, 3) AS DATE)                AS dt,
    instrument_id,
    venue,
    CAST(TO_TIMESTAMP_LTZ(event_time_us / 1000, 3) AS TIMESTAMP(3))        AS event_time,
    CAST(TO_TIMESTAMP_LTZ(ingest_time_us / 1000, 3) AS TIMESTAMP(3))       AS ingest_time,
    price,
    `size`,
    side,
    `sequence`,
    ingest_time_us - event_time_us                                         AS latency_us
FROM ticks_src;

INSERT INTO iceberg.market.bars
SELECT
    CAST(TO_TIMESTAMP_LTZ(window_start_ms, 3) AS DATE)                     AS dt,
    instrument_id,
    bar_interval,
    CAST(TO_TIMESTAMP_LTZ(window_start_ms, 3) AS TIMESTAMP(3))             AS window_start,
    CAST(TO_TIMESTAMP_LTZ(window_end_ms, 3) AS TIMESTAMP(3))               AS window_end,
    `open`, high, low, `close`, volume, vwap, trades
FROM bars_src;

END;
