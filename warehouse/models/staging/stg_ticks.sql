-- Silver: trades, typed and with the late ones marked rather than removed.
--
-- A trade that missed its window is still a real trade. Dropping it here would
-- hide the cost of the watermark delay; keeping it unmarked would let it leak
-- into aggregates that Flink deliberately excluded. So it is kept and flagged,
-- and every downstream model chooses explicitly.
--
-- was_late is a tuple IN, not a LEFT JOIN. ClickHouse does not produce NULLs
-- for unmatched left-join rows unless join_use_nulls is set: it fills the
-- column's default, which for String is ''. So `l.sequence is not null` was
-- true for EVERY row and the first build of fct_pipeline_health reported a
-- late rate of exactly 1.0 across every day.
with ticks as (
    select * from {{ source('market', 'ticks') }}
)

select
    t.instrument_id,
    t.venue,
    t.event_time,
    t.ingest_time,
    toDate(t.event_time)                      as trade_date,
    t.price,
    t.size,
    t.price * t.size                          as notional,
    t.side,
    t.sequence,
    t.latency_us,
    t.latency_us / 1000.0                     as latency_ms,
    (t.instrument_id, t.sequence) in (
        select instrument_id, sequence
        from {{ source('market', 'ticks_late') }}
    )                                         as was_late
from ticks as t
