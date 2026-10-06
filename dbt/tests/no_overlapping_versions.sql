with versions as (
 select *, lead(valid_from) over(partition by customer_id order by valid_from) as next_from
 from {{ ref('dim_customer_scd2') }}
)
select * from versions
where (valid_to is not null and valid_to<=valid_from)
 or (next_from is not null and (valid_to is null or valid_to>next_from))
