-- ───────────────────────────────────────────────────────────────────────────
-- Event-time OHLCV bars, and the late trades that missed them.
--
-- This is the part Phase 1 did not have. Phase 1 aggregated bars on READ
-- (market.bars_1m_live), which means a "bar" was whatever happened to have
-- arrived in ClickHouse when the query ran. Re-run the same query a second
-- later and a bar for a window ten minutes old could still change.
--
-- Here a bar is closed by the WATERMARK: Flink emits it once it believes no
-- more trades for that window are coming. Trades that show up anyway are late,
-- and are routed to ticks.late rather than silently dropped or silently
-- folded into a bar that consumers have already acted on.
-- ───────────────────────────────────────────────────────────────────────────

SET 'pipeline.name' = 'mdp-bars';
-- Everything downstream assumes UTC; make the session agree rather than
-- inheriting whatever the container's clock says.
SET 'table.local-time-zone' = 'UTC';
SET 'execution.runtime-mode' = 'streaming';

-- Without this, nothing is ever emitted.
--
-- A watermark is the MINIMUM across all source subtasks. ticks.raw has 3
-- partitions and 3 instruments, which hash onto only 2 of them, so partition 1
-- is permanently empty. An empty partition never advances its watermark, the
-- minimum stays pinned, no window ever closes, and the job sits there RUNNING
-- and perfectly healthy while producing nothing.
--
-- idle-timeout marks a quiet partition as idle so it stops holding the
-- watermark back. This is the single most common reason a correct-looking
-- Flink job emits no output.
SET 'table.exec.source.idle-timeout' = '10s';

-- ─── source ───────────────────────────────────────────────────────────────

CREATE TABLE ticks (
    instrument_id   STRING,
    venue           STRING,
    event_time_us   BIGINT,
    ingest_time_us  BIGINT,
    price           DOUBLE,
    `size`          DOUBLE,
    side            STRING,
    `sequence`      STRING,

    -- The venue's clock is the event time. Wall clock is never used for
    -- windowing: that is the whole distinction Phase 1 was missing.
    event_time AS TO_TIMESTAMP_LTZ(event_time_us / 1000, 3),

    -- How long we are willing to wait for stragglers before closing a window.
    -- 5s is a deliberate trade-off: longer means fewer late trades but slower
    -- bars. market.ticks_late is how we find out whether it was right.
    WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'ticks.raw',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-bars-v1',
    'scan.startup.mode' = 'latest-offset',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081'
);

-- ─── sinks ────────────────────────────────────────────────────────────────

CREATE TABLE bars_1m (
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
    'topic' = 'bars.1m',
    'properties.bootstrap.servers' = 'kafka:9092',
    'key.format' = 'raw',
    'key.fields' = 'instrument_id',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081',
    'value.fields-include' = 'ALL'
);

CREATE TABLE bars_5m (
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
    'topic' = 'bars.5m',
    'properties.bootstrap.servers' = 'kafka:9092',
    'key.format' = 'raw',
    'key.fields' = 'instrument_id',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081',
    'value.fields-include' = 'ALL'
);

CREATE TABLE ticks_late (
    instrument_id   STRING,
    venue           STRING,
    event_time_us   BIGINT,
    ingest_time_us  BIGINT,
    price           DOUBLE,
    `size`          DOUBLE,
    side            STRING,
    `sequence`      STRING,
    lateness_ms     BIGINT
) WITH (
    'connector' = 'kafka',
    'topic' = 'ticks.late',
    'properties.bootstrap.servers' = 'kafka:9092',
    'key.format' = 'raw',
    'key.fields' = 'instrument_id',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081',
    'value.fields-include' = 'ALL'
);

-- ─── the jobs ─────────────────────────────────────────────────────────────
-- One statement set, so all three run in a single job sharing one read of
-- ticks.raw rather than three independent consumers of the same topic.

EXECUTE STATEMENT SET
BEGIN

INSERT INTO bars_1m
SELECT
    instrument_id,
    '1m' AS bar_interval,
    CAST(UNIX_TIMESTAMP(DATE_FORMAT(window_start, 'yyyy-MM-dd HH:mm:ss')) AS BIGINT) * 1000,
    CAST(UNIX_TIMESTAMP(DATE_FORMAT(window_end,   'yyyy-MM-dd HH:mm:ss')) AS BIGINT) * 1000,
    -- open/close rest on an invariant rather than an ORDER BY: this Flink
    -- build has no MIN_BY/MAX_BY, and FIRST_VALUE/LAST_VALUE order by
    -- ARRIVAL, not event time. Arrival order equals event-time order here
    -- because: Coinbase emits trades per product in sequence on one socket;
    -- the producer keys by instrument_id so they land in one partition; and
    -- Kafka preserves order within a partition. If that invariant ever
    -- breaks, the offending trade is late by definition and shows up in
    -- market.ticks_late — which is how we find out rather than assume.
    FIRST_VALUE(price)         AS `open`,
    MAX(price)                 AS high,
    MIN(price)                 AS low,
    LAST_VALUE(price)          AS `close`,
    SUM(`size`)                AS volume,
    SUM(price * `size`) / NULLIF(SUM(`size`), 0) AS vwap,
    COUNT(*)                   AS trades
FROM TABLE(TUMBLE(TABLE ticks, DESCRIPTOR(event_time), INTERVAL '1' MINUTE))
GROUP BY instrument_id, window_start, window_end;

INSERT INTO bars_5m
SELECT
    instrument_id,
    '5m' AS bar_interval,
    CAST(UNIX_TIMESTAMP(DATE_FORMAT(window_start, 'yyyy-MM-dd HH:mm:ss')) AS BIGINT) * 1000,
    CAST(UNIX_TIMESTAMP(DATE_FORMAT(window_end,   'yyyy-MM-dd HH:mm:ss')) AS BIGINT) * 1000,
    FIRST_VALUE(price)         AS `open`,
    MAX(price)                 AS high,
    MIN(price)                 AS low,
    LAST_VALUE(price)          AS `close`,
    SUM(`size`)                AS volume,
    SUM(price * `size`) / NULLIF(SUM(`size`), 0) AS vwap,
    COUNT(*)                   AS trades
FROM TABLE(TUMBLE(TABLE ticks, DESCRIPTOR(event_time), INTERVAL '5' MINUTE))
GROUP BY instrument_id, window_start, window_end;

-- Late arrivals. CURRENT_WATERMARK() is how Flink SQL exposes the watermark to
-- a query; a row whose event time is already behind it cannot reach its window.
INSERT INTO ticks_late
SELECT
    instrument_id,
    venue,
    event_time_us,
    ingest_time_us,
    price,
    `size`,
    side,
    `sequence`,
    CAST(TIMESTAMPDIFF(SECOND, event_time, CURRENT_WATERMARK(event_time)) AS BIGINT) * 1000
        AS lateness_ms
FROM ticks
WHERE CURRENT_WATERMARK(event_time) IS NOT NULL
  AND event_time < CURRENT_WATERMARK(event_time);

END;
