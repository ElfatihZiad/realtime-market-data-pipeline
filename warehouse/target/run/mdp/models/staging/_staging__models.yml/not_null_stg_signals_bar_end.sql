
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select bar_end
from `market_staging`.`stg_signals`
where bar_end is null



  
  
    ) dbt_internal_test