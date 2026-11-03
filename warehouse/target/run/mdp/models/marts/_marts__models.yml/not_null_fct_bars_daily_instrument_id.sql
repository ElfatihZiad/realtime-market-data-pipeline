
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select instrument_id
from `market_marts`.`fct_bars_daily`
where instrument_id is null



  
  
    ) dbt_internal_test