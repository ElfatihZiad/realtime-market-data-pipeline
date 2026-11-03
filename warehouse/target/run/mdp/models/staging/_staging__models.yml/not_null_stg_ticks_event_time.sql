
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select event_time
from `market_staging`.`stg_ticks`
where event_time is null



  
  
    ) dbt_internal_test