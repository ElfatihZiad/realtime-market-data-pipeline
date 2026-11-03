
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select trades
from `market_marts`.`fct_instrument_liquidity`
where trades is null



  
  
    ) dbt_internal_test