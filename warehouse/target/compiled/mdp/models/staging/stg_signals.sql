-- Silver: per-bar volatility and spike flags.
select
    instrument_id,
    bar_end,
    toDate(bar_end) as trade_date,
    close,
    log_return,
    realized_vol,
    zscore,
    is_spike
from `market`.`signals` final