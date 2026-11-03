
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select trades
from `market_staging`.`stg_bars`
where trades is null



  
  
    ) dbt_internal_test