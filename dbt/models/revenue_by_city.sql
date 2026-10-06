select customer_city_at_order, count(*) as order_count, sum(order_amount) as revenue
from {{ ref('fact_orders') }}
group by customer_city_at_order
