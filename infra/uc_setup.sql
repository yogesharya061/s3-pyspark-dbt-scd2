-- Run as a Unity Catalog administrator AFTER creating an AWS storage credential.
-- Replace ALL angle-bracket placeholders. Use a dedicated non-overlapping prefix.
CREATE EXTERNAL LOCATION portfolio_dev
URL 's3://<bucket>/portfolio/dev'
WITH (STORAGE CREDENTIAL `<storage_credential>`);

GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION portfolio_dev TO `<schema_owner>`;
CREATE SCHEMA `<catalog>`.portfolio_dev_silver;
CREATE SCHEMA `<catalog>`.portfolio_dev_gold
MANAGED LOCATION 's3://<bucket>/portfolio/dev/gold-managed';

GRANT USE CATALOG ON CATALOG `<catalog>` TO `<runner>`;
GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA `<catalog>`.portfolio_dev_silver TO `<runner>`;
GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA `<catalog>`.portfolio_dev_gold TO `<runner>`;
GRANT READ FILES, WRITE FILES, CREATE EXTERNAL TABLE ON EXTERNAL LOCATION portfolio_dev TO `<runner>`;
-- Repeat with portfolio_prod and a /prod prefix for production.
-- Do NOT put an external volume at the lake root: it would overlap the table paths.
