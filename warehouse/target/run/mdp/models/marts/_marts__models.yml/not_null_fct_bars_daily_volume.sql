
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select volume
from `market_marts`.`fct_bars_daily`
where volume is null



  
  
    ) dbt_internal_test