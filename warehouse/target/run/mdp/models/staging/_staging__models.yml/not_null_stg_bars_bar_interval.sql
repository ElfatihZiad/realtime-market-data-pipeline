
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select bar_interval
from `market_staging`.`stg_bars`
where bar_interval is null



  
  
    ) dbt_internal_test