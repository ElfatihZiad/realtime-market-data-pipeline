-- ───────────────────────────────────────────────────────────────────────────
-- News sentiment joined to price, on event time.
--
-- This is a stream-to-stream WINDOW JOIN: two independent streams, each with
-- its own watermark, aligned on the same 5-minute event-time windows. It is
-- the hardest thing in this repo and the reason the phase exists.
--
-- Why a window join and not a regular one: a regular join on window_start
-- would be an unbounded stateful join producing UPDATING rows, which an
-- append-only Kafka sink rejects. A window join is bounded — once the
-- watermark passes a window, that window's state is released — and its output
-- is append-only by construction.
--
-- The bars side keys on window_START, not window_end. A 5m bar for
-- [10:00, 10:05) has window_end 10:05, which TUMBLE would place in the NEXT
-- window. Keying on the start makes each bar land in exactly its own window
-- and aligns the two sides on the same boundaries.
-- ───────────────────────────────────────────────────────────────────────────

SET 'pipeline.name' = 'mdp-sentiment';
SET 'table.local-time-zone' = 'UTC';
SET 'execution.runtime-mode' = 'streaming';
SET 'table.exec.source.idle-timeout' = '10s';

-- ─── sources ──────────────────────────────────────────────────────────────

CREATE TABLE news_src (
    article_id       STRING,
    instrument_id    STRING,
    source           STRING,
    title            STRING,
    url              STRING,
    published_at_us  BIGINT,
    ingest_time_us   BIGINT,
    sentiment        DOUBLE,
    scorer           STRING,

    published_at AS TO_TIMESTAMP_LTZ(published_at_us / 1000, 3),
    -- News is far laggier than trades: feeds publish on their own schedule and
    -- we poll every few minutes. 10 minutes of slack, against 5 seconds for
    -- ticks, is the honest number for this source.
    WATERMARK FOR published_at AS published_at - INTERVAL '10' MINUTE
) WITH (
    'connector' = 'kafka',
    'topic' = 'news.raw',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-sentiment-news-v1',
    'scan.startup.mode' = 'earliest-offset',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081'
);

CREATE TABLE bars5_src (
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

    bar_start AS TO_TIMESTAMP_LTZ(window_start_ms, 3),
    WATERMARK FOR bar_start AS bar_start - INTERVAL '1' MINUTE
) WITH (
    'connector' = 'kafka',
    'topic' = 'bars.5m',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-sentiment-bars-v1',
    'scan.startup.mode' = 'earliest-offset',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081'
);

-- ─── sink ─────────────────────────────────────────────────────────────────

CREATE TABLE sentiment_sink (
    instrument_id    STRING,
    window_start_ms  BIGINT,
    window_end_ms    BIGINT,
    articles         BIGINT,
    avg_sentiment    DOUBLE,
    min_sentiment    DOUBLE,
    max_sentiment    DOUBLE,
    `open`           DOUBLE,
    `close`          DOUBLE,
    return_pct       DOUBLE,
    volume           DOUBLE,
    trades           BIGINT
) WITH (
    'connector' = 'kafka',
    'topic' = 'sentiment.5m',
    'properties.bootstrap.servers' = 'kafka:9092',
    'key.format' = 'raw',
    'key.fields' = 'instrument_id',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.url' = 'http://schema-registry:8081',
    'value.fields-include' = 'ALL'
);

-- ─── the join ─────────────────────────────────────────────────────────────
-- INNER: a window is emitted only when BOTH sides have something in it. Most
-- 5-minute windows contain trades but no news, and a row claiming "sentiment
-- 0.0" for a window where nothing was published would be a fabricated
-- reading, not a neutral one.

INSERT INTO sentiment_sink
SELECT
    b.instrument_id,
    CAST(UNIX_TIMESTAMP(DATE_FORMAT(b.window_start, 'yyyy-MM-dd HH:mm:ss')) AS BIGINT) * 1000,
    CAST(UNIX_TIMESTAMP(DATE_FORMAT(b.window_end,   'yyyy-MM-dd HH:mm:ss')) AS BIGINT) * 1000,
    n.articles,
    n.avg_sentiment,
    n.min_sentiment,
    n.max_sentiment,
    b.`open`,
    b.`close`,
    b.`close` / NULLIF(b.`open`, 0) - 1  AS return_pct,
    b.volume,
    b.trades
FROM (
    SELECT
        window_start,
        window_end,
        instrument_id,
        COUNT(*)        AS articles,
        AVG(sentiment)  AS avg_sentiment,
        MIN(sentiment)  AS min_sentiment,
        MAX(sentiment)  AS max_sentiment
    FROM TABLE(TUMBLE(TABLE news_src, DESCRIPTOR(published_at), INTERVAL '5' MINUTE))
    GROUP BY window_start, window_end, instrument_id
) n
JOIN (
    SELECT
        window_start,
        window_end,
        instrument_id,
        -- One 5m bar per window per instrument, so these aggregates pick that
        -- single row; they exist to satisfy GROUP BY, not to combine anything.
        MAX(`open`)   AS `open`,
        MAX(`close`)  AS `close`,
        MAX(volume)   AS volume,
        MAX(trades)   AS trades
    FROM TABLE(TUMBLE(TABLE bars5_src, DESCRIPTOR(bar_start), INTERVAL '5' MINUTE))
    WHERE bar_interval = '5m'
    GROUP BY window_start, window_end, instrument_id
) b
  ON  n.instrument_id = b.instrument_id
  AND n.window_start  = b.window_start
  AND n.window_end    = b.window_end;
