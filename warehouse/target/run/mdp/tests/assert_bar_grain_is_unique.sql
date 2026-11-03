
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- A bar is identified by (instrument, interval, window start). Two rows at
-- that grain means the dedup in stg_bars failed, or two Flink jobs were
-- writing the same topic — which is exactly what happened once during
-- development when a job was submitted twice.
select
    instrument_id,
    bar_interval,
    window_start,
    count() as n
from `market_staging`.`stg_bars`
group by instrument_id, bar_interval, window_start
having n > 1
  
  
    ) dbt_internal_test