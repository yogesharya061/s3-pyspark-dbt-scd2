#!/usr/bin/env bash
set -euo pipefail
batch="${1:?batch ID required}"
: "${LAKE_ROOT:?Set LAKE_ROOT}"
: "${DBT_ACCESS_TOKEN:?Set DBT_ACCESS_TOKEN}"
# Caller must serialize this COMPLETE sequence. Spark max_concurrent_runs alone is insufficient.
if [[ "${USE_FIXTURES:-0}" == 1 ]]; then
  python -m scripts.ingest_sources --fixtures --batch "$batch" --root "$LAKE_ROOT"
else
  python -m scripts.ingest_sources --batch "$batch" --root "$LAKE_ROOT"
fi
databricks bundle run -t "${DEPLOY_TARGET:-dev}" silver --params "batch_id=$batch"
cd dbt
dbt test --profiles-dir . --target cloud --select 'source:*' --indirect-selection cautious
dbt snapshot --profiles-dir . --target cloud
dbt run --profiles-dir . --target cloud
dbt test --profiles-dir . --target cloud
