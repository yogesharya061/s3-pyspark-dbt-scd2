select dbt_scd_id as customer_version_key, customer_id, name, email, city, tier,
       is_deleted, dbt_valid_from as valid_from, dbt_valid_to as valid_to,
       case when dbt_valid_to is null then true else false end as is_current
from {{ ref('customer_history') }}
