-- Gold: how tradeable each instrument actually was, per day.
--
-- Uses stg_ticks including late arrivals: this is a question about the market,
-- not about our windowing, so a trade that reached us late still happened.
select
    instrument_id,
    trade_date,
    count()                                   as trades,
    countIf(was_late)                         as late_trades,
    sum(size)                                 as volume,
    sum(notional)                             as notional,
    avg(size)                                 as avg_trade_size,
    quantile(0.5)(size)                       as median_trade_size,
    quantile(0.99)(size)                      as p99_trade_size,
    countIf(side = 'buy')                     as buy_trades,
    countIf(side = 'sell')                    as sell_trades,
    (countIf(side = 'buy') - countIf(side = 'sell'))
        / nullIf(count(), 0)                  as order_flow_imbalance
from {{ ref('stg_ticks') }}
group by instrument_id, trade_date
