select 1 as mismatch
where (select count(*) from {{ source('silver','orders') }}) <> (select count(*) from {{ ref('fact_orders') }})
 or coalesce((select sum(order_amount) from {{ source('silver','orders') }}),0)
 <> coalesce((select sum(order_amount) from {{ ref('fact_orders') }}),0)
