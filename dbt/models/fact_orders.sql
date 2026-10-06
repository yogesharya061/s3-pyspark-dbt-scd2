select o.order_id, o.customer_id, o.product_id, o.ordered_at, o.quantity,
       o.unit_price, o.order_amount, p.product_name, p.category,
       c.customer_version_key, c.city as customer_city_at_order,
       c.tier as customer_tier_at_order
from {{ source('silver','orders') }} o
left join {{ source('silver','products') }} p on o.product_id=p.product_id
left join {{ ref('dim_customer_scd2') }} c
 on o.customer_id=c.customer_id
 and o.ordered_at>=c.valid_from
 and (o.ordered_at<c.valid_to or c.valid_to is null)
 and c.is_deleted=false
