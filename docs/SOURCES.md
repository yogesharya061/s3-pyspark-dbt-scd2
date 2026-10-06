# Source contracts and integration layer

## Adapters

| Source | Entity | Required fields | Extraction boundary |
|---|---|---|---|
| CSV | customers | customer_id, name, email, city, tier, is_deleted, updated_at | Full file supplied by CRM export |
| REST | orders | order_id, customer_id, product_id, quantity, unit_price, ordered_at, updated_at | Paginated immutable source batch |
| PostgreSQL | products | product_id, product_name, category, updated_at | Read-only repeatable-read SELECT |

All dates use UTC, in `YYYY-MM-DD HH:MM:SS` format for fixtures. Each ID is unique after deduplication. Timestamps must advance when business attributes change. Quantity must be a positive integer; currency is a single agreed currency and uses decimal amounts. This demo rounds unit prices to two decimals during casting; agree rounding rules before real use.

REST must return `{ "data": [ ... ], "next": "https://same-host/next-page" }`, with `next: null` on its last page. Same-origin absolute next links only; redirects and pagination loops are rejected. Retry is bounded for 429 and transient 5xx responses; permanent failures prevent publishing a manifest. The source must guarantee a stable pagination view (for example a batch or snapshot token); the connector cannot manufacture API consistency.

Create the PostgreSQL source table:

```sql
CREATE TABLE public.products (
 product_id text PRIMARY KEY,
 product_name text NOT NULL,
 category text NOT NULL,
 updated_at timestamp NOT NULL
);
INSERT INTO public.products VALUES
 ('P1','Notebook','Stationery','2026-01-01 00:00:00'),
 ('P2','Pen set','Stationery','2026-01-01 00:00:00');
```

Use a read-only database account. Set `CUSTOMERS_CSV`, `ORDERS_API_URL`, `ORDERS_API_TOKEN` and `POSTGRES_DSN` securely, then:

```bash
python -m scripts.ingest_sources --root s3://YOUR_BUCKET/portfolio/dev --batch your_unique_batch
```

Credentials use the AWS SDK default chain; no AWS keys are in the code. `--fixtures` exercises the same landing writer with local synthetic records. It bypasses live source adapters. The CI suite separately exercises actual HTTP pagination and actual PostgreSQL extraction.

## Landing layout

```text
s3://BUCKET/portfolio/dev/bronze/batch_001/customers.jsonl
s3://BUCKET/portfolio/dev/bronze/batch_001/orders.jsonl
s3://BUCKET/portfolio/dev/bronze/batch_001/products.jsonl
s3://BUCKET/portfolio/dev/bronze/batch_001/manifest.json
s3://BUCKET/portfolio/dev/silver/customers/
s3://BUCKET/portfolio/dev/silver/orders/
s3://BUCKET/portfolio/dev/silver/products/
s3://BUCKET/portfolio/dev/quarantine/batch_001/customers/
s3://BUCKET/portfolio/dev/gold-managed/  (Unity Catalog owns physical table directories)
```

Canonical JSON preserves required source fields as strings and excludes extra columns. This is a normalized raw landing format, not a byte-for-byte copy of source files. The manifest has object keys, row counts and hashes, and is written only after all entities land. Reusing a batch ID with different data fails. An interrupted landing can be retried with identical data; a changed payload needs a new batch ID.

The current adapters collect each entity in memory and do full source extracts; no CDC or persistent watermark is claimed. For large sources add streaming/multipart writes, partitioned extraction, API batch tokens or database CDC, and source-specific checkpoints. Checksums in the cloud notebook also assume small objects. Size-bound this demo before adapting it to production.

The three sources are extracted sequentially and are not one cross-system transaction. Agree a common batch cutoff or source snapshot tokens when cross-source consistency is required. Orders without a matching customer/product fail Gold tests.
