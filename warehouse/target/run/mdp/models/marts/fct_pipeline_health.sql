
  
    
    
    
        


        
  

  insert into `market_marts`.`fct_pipeline_health__dbt_backup`
        ("trade_date", "instruments", "ticks", "bars", "late_ticks", "late_rate", "decode_errors", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "max_latency_ms")-- Gold: the pipeline's own report card.
--
-- Most portfolio projects can tell you what the data says. Rather fewer can
-- tell you how late it was, how much of it missed its window, and how much
-- never parsed at all. That is this table.
with ticks as (
    select
        trade_date,
        count()                         as ticks,
        countIf(was_late)               as late_ticks,
        quantile(0.5)(latency_ms)       as p50_latency_ms,
        quantile(0.95)(latency_ms)      as p95_latency_ms,
        quantile(0.99)(latency_ms)      as p99_latency_ms,
        max(latency_ms)                 as max_latency_ms,
        uniqExact(instrument_id)        as instruments
    from `market_staging`.`stg_ticks`
    group by trade_date
),

bars as (
    select trade_date, count() as bars
    from `market_staging`.`stg_bars`
    where bar_interval = '1m'
    group by trade_date
),

decode_errors as (
    select toDate(occurred_at) as trade_date, count() as decode_errors
    from `market`.`ticks_errors`
    group by trade_date
)

select
    t.trade_date                                     as trade_date,
    t.instruments                                    as instruments,
    t.ticks                                          as ticks,
    coalesce(b.bars, 0)                              as bars,
    t.late_ticks                                     as late_ticks,
    t.late_ticks / nullIf(t.ticks, 0)                as late_rate,
    coalesce(e.decode_errors, 0)                     as decode_errors,
    t.p50_latency_ms                                 as p50_latency_ms,
    t.p95_latency_ms                                 as p95_latency_ms,
    t.p99_latency_ms                                 as p99_latency_ms,
    t.max_latency_ms                                 as max_latency_ms
from ticks as t
left join bars as b on t.trade_date = b.trade_date
left join decode_errors as e on t.trade_date = e.trade_date
  