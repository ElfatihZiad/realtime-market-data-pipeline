
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- A trade whose venue timestamp is in our future means a clock problem
-- somewhere, and would silently corrupt every event-time window.
select instrument_id, event_time, ingest_time
from `market_staging`.`stg_ticks`
where event_time > ingest_time + interval 5 second
  
  
    ) dbt_internal_test