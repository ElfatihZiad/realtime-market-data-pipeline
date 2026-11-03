
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- A volume-weighted average price cannot fall outside the bar's own range.
-- A tiny tolerance absorbs float rounding; see ADR 0007 on price as double.
select
    instrument_id,
    bar_interval,
    window_start,
    low, vwap, high
from `market_staging`.`stg_bars`
where volume > 0
  and (vwap < low - 1e-6 or vwap > high + 1e-6)
  
  
    ) dbt_internal_test