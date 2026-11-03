-- Gold: one row per instrument per day, rolled up from the 1m bars.
--
-- Built from bars rather than from ticks on purpose. The bars are already
-- watermark-closed, so this inherits that completeness instead of re-deciding
-- what "the end of the day" means.
with bars as (
    select *
    from `market_staging`.`stg_bars`
    where bar_interval = '1m'
)

-- Every column is qualified with `b.`: ClickHouse resolves a bare `volume`
-- against the output alias `volume`, decides `sum(volume)` is nested inside
-- another aggregate, and rejects the query.
select
    b.instrument_id                                    as instrument_id,
    b.trade_date                                       as trade_date,
    min(b.window_start)                                as first_bar_at,
    max(b.window_start)                                as last_bar_at,
    count()                                            as bars,
    sum(b.trades)                                      as trades,
    argMin(b.open, b.window_start)                     as open,
    max(b.high)                                        as high,
    min(b.low)                                         as low,
    argMax(b.close, b.window_start)                    as close,
    sum(b.volume)                                      as volume,
    sum(b.vwap * b.volume) / nullIf(sum(b.volume), 0)  as vwap,
    argMax(b.close, b.window_start)
        / nullIf(argMin(b.open, b.window_start), 0) - 1 as return_pct
from bars as b
group by b.instrument_id, b.trade_date