
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- high must be the highest and low the lowest, and open/close must sit
-- between them. If windowing or the open/close ordering invariant breaks,
-- this is where it shows up.
select
    instrument_id,
    bar_interval,
    window_start,
    open, high, low, close
from `market_staging`.`stg_bars`
where high < low
   or open > high or open < low
   or close > high or close < low
  
  
    ) dbt_internal_test