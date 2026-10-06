{% snapshot customer_history %}
{{ config(target_schema=target.schema, unique_key='customer_id', strategy='timestamp', updated_at='updated_at', invalidate_hard_deletes=False) }}
select customer_id, name, email, city, tier, is_deleted, updated_at
from {{ source('silver','customers') }}
{% endsnapshot %}
