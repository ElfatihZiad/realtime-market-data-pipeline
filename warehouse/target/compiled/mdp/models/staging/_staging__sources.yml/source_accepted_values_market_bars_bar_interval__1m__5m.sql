
    
    

with all_values as (

    select
        bar_interval as value_field,
        count(*) as n_records

    from `market`.`bars`
    group by bar_interval

)

select *
from all_values
where value_field not in (
    '1m','5m'
)


