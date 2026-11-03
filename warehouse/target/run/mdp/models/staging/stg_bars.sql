

  create or replace view `market_staging`.`stg_bars` 
  
    
  
  
    
    
  as (
    -- Silver: Flink's event-time bars, deduplicated.
--
-- market.bars is a ReplacingMergeTree, so a re-delivered bar may exist twice
-- until a background merge collapses it. FINAL forces that at read time — the
-- grain below is relied on by the marts and by the uniqueness test.
select
    instrument_id,
    bar_interval,
    window_start,
    window_end,
    toDate(window_start) as trade_date,
    open,
    high,
    low,
    close,
    volume,
    vwap,
    trades
from `market`.`bars` final
    
  )
      
      
                    -- end_of_sql
                    
                    