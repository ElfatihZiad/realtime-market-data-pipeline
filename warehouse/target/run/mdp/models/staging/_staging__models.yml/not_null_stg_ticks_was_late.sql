
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select was_late
from `market_staging`.`stg_ticks`
where was_late is null



  
  
    ) dbt_internal_test