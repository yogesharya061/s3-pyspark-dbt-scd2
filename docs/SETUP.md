# Complete setup sequence

## 1. Local prerequisites

Install Python 3.12 and Java 17; verify `python --version` and `java -version`. Create a virtual environment and install `requirements-local.txt`. Run commands from repository root unless a command says `cd dbt`. Use `python -m scripts.demo` for the offline source fixtures, actual Spark processing and actual dbt SCD2 snapshots. Docker is not required for that path.

CI starts PostgreSQL 16 as a temporary service to test the live database adapter. To run this test locally, start your own PostgreSQL instance, create a disposable database, set `POSTGRES_TEST_DSN`, and run pytest. The test creates a `products` table and inserts P1 in that disposable database.

## 2. AWS S3 bucket

Requires AWS CLI authentication and Terraform >=1.6. The Terraform creates a private versioned S3 bucket, AES256 server-side encryption and a deny-non-TLS bucket policy. It does not create a Databricks workspace, IAM admin identity or network.

```bash
cd infra
terraform init
cp terraform.tfvars.example demo.tfvars
# Edit region and globally unique bucket_name in demo.tfvars.
terraform plan -var-file=demo.tfvars -out=demo.tfplan
terraform apply demo.tfplan
cd ..
```

Keep tfvars/state out of commits. Use an encrypted remote state backend with locking for team deployments. Terraform plan/apply is a separate reviewed infrastructure step, not automatically executed by the application CD workflow. `force_destroy=false` prevents automatic removal of a nonempty bucket. Review costs and cleanup deliberately.

## 3. Databricks prerequisites and S3 access

Use an existing **Databricks on AWS** workspace enabled for Unity Catalog, attached to a metastore. Required compute:

- UC-enabled all-purpose cluster, DBR 15.4 LTS or a tested compatible runtime, Python supported by that runtime.
- SQL warehouse accessible to the dbt identity; record its hostname and HTTP path.
- Existing catalog such as `portfolio`; permissions to create the demo schemas.

Create an AWS IAM role for Unity Catalog following the current Databricks S3 storage-credential wizard. The wizard supplies the correct Databricks principal and external ID for the role trust policy; do not substitute the GitHub OIDC trust for it. Include the documented self-assume trust requirement. Grant that role the documented S3 bucket/list/object permissions on `portfolio/dev/*` and later a separately reviewed production prefix. If using KMS instead of this demo's AES256 encryption, add the necessary KMS key policy and permissions.

In Catalog Explorer → External Data → Credentials, create an AWS IAM-role storage credential using that role ARN, finish the external-ID trust update, and validate it. Then edit and run `infra/uc_setup.sql` as a UC administrator. It creates an external location and two schemas and grants the runner access.

**Storage separation matters:** Bronze, Silver, quarantine and Gold-managed prefixes must not overlap table/volume roots. The Gold schema uses `MANAGED LOCATION` in the S3 bucket; dbt-managed Delta tables, including the snapshot, inherit that location. Do not directly edit managed table files.

Official step-by-step credential setup:
https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/s3/s3-external-location-manual

## 4. Identities and permissions

| Identity | Purpose | Minimum scope to configure |
|---|---|---|
| Source extractor | Reads CSV/API/database and writes Bronze | Read-only API/database; S3 list/get/put on Bronze prefix |
| UC storage IAM role | Databricks accesses lake files | S3 permissions and role trust required by UC setup |
| Databricks runner | Runs Spark job and dbt SQL | Cluster attach, job ownership/run, CAN USE warehouse, catalog/schema/table and external-location grants |
| GitHub OIDC role | Temporary AWS auth in CD | Trust restricted to this repository and chosen environment; Bronze S3 policy |

Use the placeholder policies under `infra/` as scoped examples. Replace bucket/account/role names and have an administrator review them. Add a separate production role/trust subject for environment `prod`. Do not attach administrator permissions for convenience.

The project uses a scoped Databricks token from a protected secret for simple setup. For enterprise operation migrate to your approved OAuth/workload-identity configuration, test dbt authentication and rotate/revoke any temporary token. Never put secrets in `.env.example`, source files, notebook cells or workflow logs.

## 5. Configure and deploy application artifacts

Install the current official Databricks CLI supporting bundles. In a **separate cloud virtual environment**, install `requirements-cloud.txt`; do not mix adapters if dependency resolution conflicts with the local environment.

Copy the variable names from `.env.example` into your secure shell/session configuration. `DATABRICKS_HOST` includes `https://`; `DBT_DATABRICKS_HOST` is hostname only. `BUNDLE_VAR_lake_root` and `LAKE_ROOT` must match. Gold and Silver schemas must match the setup SQL.

```bash
# With all required environment variables populated securely:
databricks bundle validate -t dev
databricks bundle deploy -t dev
```

Deploy uploads the notebook, its shared package and a job. It does not execute paid compute.

## 6. Run two synthetic cloud batches

```bash
export USE_FIXTURES=1
export DEPLOY_TARGET=dev
bash scripts/cloud_batch.sh batch_001
# Only after the entire first command succeeds:
bash scripts/cloud_batch.sh batch_002
```

Each command lands Bronze, waits for the Spark job, tests Silver, snapshots customer history, builds Gold and runs all dbt tests. Do not run these sequences concurrently. To try a repeat after batch 2, rerun batch_002; do not replay older batch_001 into current Silver.

Verify in SQL warehouse:

```sql
SELECT customer_id, city, tier, valid_from, valid_to, is_current
FROM <catalog>.portfolio_dev_gold.dim_customer_scd2
ORDER BY customer_id, valid_from;
SELECT order_id, customer_city_at_order, order_amount
FROM <catalog>.portfolio_dev_gold.fact_orders ORDER BY order_id;
```

Expected: three customer history rows, two current customers, O1 Delhi 100.00, O2 Mumbai 80.00.

## 7. Connect real sources

Provide a sanitized CSV export at `CUSTOMERS_CSV`, an API matching the documented envelope, and a PostgreSQL table matching the source contract. Configure TLS and secrets, set `USE_FIXTURES=0`, and choose a **new** batch ID. Run in a dedicated demo environment first. GitHub-hosted runners must be able to reach each source; use a private/self-hosted runner for internal endpoints. Place the CSV on that runner via your approved secure transfer before executing the workflow. Never commit customer exports just to make CI reach them.

## 8. Generate dbt documentation

```bash
cd dbt
dbt docs generate --profiles-dir . --target cloud
dbt docs serve --profiles-dir . --port 8080
```

For local docs use `--target local`; set `LOCAL_DB_PATH` if not using the default `.local` layout. Do not expose generated metadata or a development docs server publicly when real schema/data information is present.

## Cleanup

Stop/terminate unused cluster/warehouse compute. Remove the demo job with a reviewed `databricks bundle destroy -t dev` if desired; this does not remove source data or Gold history. Review tables, external paths and retained versions separately before deleting them. Do not run blanket bucket deletes; versioned object cleanup needs explicit review.
