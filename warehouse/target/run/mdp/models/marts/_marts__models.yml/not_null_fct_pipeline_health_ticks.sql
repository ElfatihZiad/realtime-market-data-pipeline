
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select ticks
from `market_marts`.`fct_pipeline_health`
where ticks is null



  
  
    ) dbt_internal_test