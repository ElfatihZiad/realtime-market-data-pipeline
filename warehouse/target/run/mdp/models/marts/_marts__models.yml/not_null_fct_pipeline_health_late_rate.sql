
    
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select late_rate
from `market_marts`.`fct_pipeline_health`
where late_rate is null



  
  
    ) dbt_internal_test