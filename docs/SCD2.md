# SCD Type 2 behavior

`customer_history` is the persisted dbt snapshot. `dim_customer_scd2` gives that history business-friendly column names. `fact_orders` joins on customer ID and a half-open time range: `ordered_at >= valid_from AND (ordered_at < valid_to OR valid_to IS NULL)`.

| Customer | City | Tier | valid_from UTC | valid_to UTC | is_current |
|---|---|---|---|---|---|
| C1 | Delhi | BASIC | 2026-01-01 00:00 | 2026-01-02 00:00 | false |
| C1 | Mumbai | GOLD | 2026-01-02 00:00 | NULL | true |
| C2 | Pune | GOLD | 2026-01-01 00:00 | NULL | true |

O1 occurred January 1 and retains Delhi/BASIC; O2 occurred January 2 and gets Mumbai/GOLD. Joining every order to today's customer record would incorrectly move O1's revenue to Mumbai.

## Rules and boundaries

- Snapshot strategy is `timestamp`, with `customer_id` as unique key and source `updated_at` as change time.
- Run a snapshot **after every successful Silver batch and before applying the next batch**. A snapshot cannot recover changes already overwritten in Silver.
- Only the newest customer version within an input batch is retained. This is an observed-state pipeline, not complete event history. If every intermediate source event matters, ingest ordered CDC events and use an event-history model instead.
- Replaying the same customer timestamp and attributes is idempotent. Stale timestamps and different attributes at equal timestamps fail before Silver writes. Resolve/replay correctly rather than silently changing historical meaning.
- Missing rows are not deletions. Silver upserts preserve them, and snapshot hard-delete invalidation is disabled. Send an explicit `is_deleted=true` update with a new timestamp for a soft delete. Its SCD2 row remains current but is excluded from the fact join for subsequent orders.
- Old orders after a deleted customer version begins fail the missing-dimension test. Investigate the source or define an approved business rule.
- A greater source timestamp creates another version even when attributes are unchanged. This is intentional timestamp-strategy behavior.
- A late order can join existing history. A retroactive customer correction is rejected and requires a reviewed history-rebuild procedure; this demo does not automate temporal corrections.
- Business keys must be globally unique per source contract. If customer sources expand, add source-system identity and a mapping process before combining keys.

## Tests

Source unique/non-null keys; unique dimension version keys; exactly one current version per customer; positive/nonoverlapping time ranges; unique order IDs; no missing temporal customer/product match; order count and amount reconciliation. The demo also asserts exact historical cities and a no-growth snapshot rerun.

Never run snapshot full-refresh or delete history to fix a failed model. Rebuild derived Gold tables from the preserved snapshot; repair the snapshot only through reviewed recovery.

Official reference: https://docs.getdbt.com/docs/build/snapshots
