# Validation scope

The project distinguishes local execution, CI integration and cloud deployment.

- Local unit/integration suite: 7 tests passed; PostgreSQL test skipped unless a disposable POSTGRES_TEST_DSN is supplied.
- HTTP pagination test uses a real local HTTP server.
- S3 conditional-write test uses a botocore Stubber; no AWS connection is made.
- Spark tests cover normalization, quarantine, conflicting same-timestamp rows, stale versions and idempotent same-version acceptance.
- Full demo runs two real Spark batches and real dbt snapshots on DuckDB, verifies historical order joins, 180.00 total revenue and no snapshot growth on rerun. See checked-in `evidence/demo-result.json` when available.
- CI includes a PostgreSQL service to exercise the database connector with a real database.

Not verified without user cloud configuration: actual AWS IAM/S3 access, Terraform apply, Databricks bundle validation/deployment, UC permissions, Delta MERGE execution on the target runtime and dbt-databricks snapshot execution. Cloud dependency resolution is checked separately from live functionality.

This is a bounded portfolio implementation, not a production certification. It deliberately omits streaming/CDC, a durable orchestration ledger, automatic temporal correction/rebuilds, enterprise secret rotation, end-user access policy enforcement, cross-table atomic publication and large-scale performance testing. Those decisions need client-specific inputs.
