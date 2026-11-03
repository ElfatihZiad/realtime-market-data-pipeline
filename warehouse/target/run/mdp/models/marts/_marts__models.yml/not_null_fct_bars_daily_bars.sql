
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select bars
from `market_marts`.`fct_bars_daily`
where bars is null



  
  
    ) dbt_internal_test