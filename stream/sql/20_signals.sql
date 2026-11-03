-- ───────────────────────────────────────────────────────────────────────────
-- Derived signals over the 1m bar stream: realized volatility and a z-score
-- spike detector.
--
-- This reads bars.1m rather than ticks.raw on purpose. The bars are already
-- watermark-closed, so everything here inherits that completeness guarantee
-- instead of re-deriving it.
-- ───────────────────────────────────────────────────────────────────────────

SET 'pipeline.name' = 'mdp-signals';
SET 'table.local-time-zone' = 'UTC';
SET 'execution.runtime-mode' = 'streaming';
SET 'table.exec.source.idle-timeout' = '10s';

CREATE TABLE bars_in (
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
    trades           BIGINT,

    -- A bar's event time is when its window ended.
    bar_time AS TO_TIMESTAMP_LTZ(window_end_ms, 3),
    WATERMARK FOR bar_time AS bar_time - INTERVAL '1' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'bars.1m',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-signals-v1',
    'scan.startup.mode' = 'latest-offset',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081'
);

CREATE TABLE signals (
    instrument_id   STRING,
    bar_end_ms      BIGINT,
    `close`         DOUBLE,
    log_return      DOUBLE,
    realized_vol    DOUBLE,
    zscore          DOUBLE,
    is_spike        BOOLEAN
) WITH (
    'connector' = 'kafka',
    'topic' = 'signals.1m',
    'properties.bootstrap.servers' = 'kafka:9092',
    'key.format' = 'raw',
    'key.fields' = 'instrument_id',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081',
    'value.fields-include' = 'ALL'
);

-- Step 1: per-bar log return. LN(close / previous close) is the standard
-- building block; realized volatility is the dispersion of these.
CREATE TEMPORARY VIEW bar_returns AS
SELECT
    instrument_id,
    bar_time,
    window_end_ms,
    `close`,
    CASE
        WHEN LAG(`close`, 1) OVER (PARTITION BY instrument_id ORDER BY bar_time) IS NULL
          OR LAG(`close`, 1) OVER (PARTITION BY instrument_id ORDER BY bar_time) <= 0
        THEN CAST(NULL AS DOUBLE)
        ELSE LN(`close` / LAG(`close`, 1) OVER (PARTITION BY instrument_id ORDER BY bar_time))
    END AS log_return
FROM bars_in;

-- Step 2: dispersion of those returns over a trailing 20-bar window, and how
-- far the latest return sits from its own recent mean.
INSERT INTO signals
SELECT
    instrument_id,
    window_end_ms AS bar_end_ms,
    `close`,
    log_return,
    STDDEV_SAMP(log_return) OVER w AS realized_vol,
    CASE
        WHEN STDDEV_SAMP(log_return) OVER w IS NULL
          OR STDDEV_SAMP(log_return) OVER w = 0
        THEN CAST(NULL AS DOUBLE)
        ELSE (log_return - AVG(log_return) OVER w) / (STDDEV_SAMP(log_return) OVER w)
    END AS zscore,
    CASE
        WHEN STDDEV_SAMP(log_return) OVER w IS NULL
          OR STDDEV_SAMP(log_return) OVER w = 0
        THEN FALSE
        ELSE ABS((log_return - AVG(log_return) OVER w) / (STDDEV_SAMP(log_return) OVER w)) > 3.0
    END AS is_spike
FROM bar_returns
WHERE log_return IS NOT NULL
WINDOW w AS (
    PARTITION BY instrument_id
    ORDER BY bar_time
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
);
