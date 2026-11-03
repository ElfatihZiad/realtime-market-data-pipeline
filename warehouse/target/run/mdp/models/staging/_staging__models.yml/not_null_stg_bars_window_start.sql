
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select window_start
from `market_staging`.`stg_bars`
where window_start is null



  
  
    ) dbt_internal_test