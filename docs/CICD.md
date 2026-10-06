# CI/CD and operations

## Pull-request and push CI

`.github/workflows/ci.yml` runs without cloud secrets:

1. Start PostgreSQL 16 for source adapter integration tests.
2. Install Python 3.12, Java 17 and pinned local dependencies.
3. Run connector, S3 request-contract and Spark tests.
4. Land synthetic batch 1, run Spark, test Silver, snapshot and build/test dbt Gold.
5. Repeat for batch 2 and assert exact historical joins.
6. Rerun snapshot and verify no additional version appears.
7. Upload run evidence as an Actions artifact.

The S3 unit test is a botocore request stub, not a real AWS write. Local Spark writes Parquet; DuckDB holds local current Silver and Gold. Live Delta/UC/S3 deployment is a separate integration boundary.

## Cloud deployment workflow

Create protected GitHub environments `dev` and `prod`. Configure required reviewers and main-branch deployment restrictions for production. The code contains workflow references, but repository/environment protection must be configured by the owner; it is not silently installed by this project.

| Environment secret | Meaning |
|---|---|
| AWS_ROLE_ARN | OIDC role scoped to that environment's Bronze prefix |
| DATABRICKS_HOST | Workspace URL including HTTPS |
| DATABRICKS_TOKEN | Scoped Databricks execution identity token |
| ORDERS_API_TOKEN | Required only for authenticated live orders API |
| POSTGRES_DSN | Read-only database DSN with verified TLS |

| Environment variable | Example/meaning |
|---|---|
| AWS_REGION | AWS region matching bucket/workspace |
| CATALOG | Existing Unity Catalog catalog |
| CLUSTER_ID | Existing UC-enabled cluster |
| LAKE_ROOT | s3://bucket/portfolio/dev or /prod |
| DBT_HOST | Workspace hostname without scheme |
| DBT_HTTP_PATH | SQL warehouse HTTP path |
| ORDERS_API_URL | Live API endpoint for non-fixture mode |
| CUSTOMERS_CSV | Path to a CSV accessible on the runner |

Configure the AWS GitHub OIDC provider, replace placeholders in `infra/github-oidc-trust.json`, and attach the scoped ingestion policy. Production needs its own role and `environment:prod` subject.

Open Actions → Deploy and run cloud batch → Run workflow. Choose `dev`, batch_001, fixtures=true. Leave `run_batch=false` for deploy-only validation. After setup is verified, choose `run_batch=true` to execute paid compute. Run batch_002 only after batch_001 completes successfully. Inputs are passed through environment variables and quoted shell arguments; the ingestion CLI validates batch IDs.

GitHub concurrency serializes the **complete** environment workflow. It is not a FIFO queue: GitHub may replace pending runs, so it is unsuitable as a source-of-truth queue for many production batches. Submit this demo one batch at a time and verify completion. For production, use a durable batch queue and orchestrator with a batch ledger/lock covering Silver and snapshots. Direct CLI users must also serialize execution. The Databricks job's max_concurrent_runs alone cannot protect the downstream snapshot sequence.

The deploy workflow does not automatically gate on a previous CI result. Require successful CI through your branch protection/review process before dispatching deployment from the chosen commit. Pin third-party Actions to reviewed commit SHAs and lock transitive dependencies when adopting the project under enterprise supply-chain controls; the demonstration uses readable upstream version tags and the official Databricks CLI action.

## Failure handling

| Failure point | Response |
|---|---|
| Source extraction | No manifest committed; correct the source and retry unchanged batch |
| Partial landing | Retry identical bytes; changed payload must use a new batch ID |
| Checksum/count failure | Stop; investigate corruption before consuming Bronze |
| Invalid rows | Inspect quarantine; default is record-level rejection, not whole-batch failure |
| Stale/ambiguous version | Stop; resolve source ordering or review a history repair |
| Silver partial write | Retry the same batch; never advance to next batch yet |
| Snapshot failure | Retry snapshot against unchanged Silver; do not apply another batch |
| Gold model/test failure | Fix model/data; rerun Gold and tests, preserving snapshot |

Cloud Delta commits are atomic **per table**, not across the three Silver tables. The local DuckDB bridge uses a transaction; this stronger local atomicity is not claimed for cloud. Gold models are rebuilt table by table and may exist before a failed quality gate completes. For production serving, publish validated versions through an approved promotion layer so readers cannot observe a partial/unvalidated refresh.

## Promotion, monitoring and rollback

Promote a reviewed Git commit from dev to prod using separate schemas/prefixes/identities. Configure job failure notifications, retry limits, retention and cloud budgets for your organization. Local/Databricks logs and dbt artifacts contain counts and test results; operational alert delivery is not implemented here.

Rollback application code by redeploying the prior known-good commit. That does not rewind source data or SCD2 history. Preserve Bronze and snapshot tables; use reviewed Delta recovery for accidental data writes. Never automate destructive snapshot resets as a normal retry.
