WITH null_check AS (
    SELECT
        'Null Key Audit' AS audit_category,
        (SELECT COUNT(*) FROM read_parquet('data/customers.parquet') WHERE customer_id IS NULL) AS missing_customer_ids,
        (SELECT COUNT(*) FROM read_parquet('data/events.parquet') WHERE event_id IS NULL OR customer_id IS NULL) AS missing_event_keys,
        (SELECT COUNT(*) FROM read_parquet('data/transactions.parquet') WHERE transaction_id IS NULL OR customer_id IS NULL) AS missing_txn_keys
),
orphan_check AS (
    SELECT
        'Referential Integrity Audit' AS audit_category,
        -- NOT EXISTS rather than NOT IN: a single NULL customer_id in the
        -- subquery would make NOT IN return zero rows for every comparison,
        -- silently reporting 0 orphans even when orphans exist.
        (SELECT COUNT(DISTINCT e.customer_id) FROM read_parquet('data/events.parquet') e
         WHERE NOT EXISTS (SELECT 1 FROM read_parquet('data/customers.parquet') c WHERE c.customer_id = e.customer_id)) AS orphan_event_customers,
        (SELECT COUNT(DISTINCT t.customer_id) FROM read_parquet('data/transactions.parquet') t
         WHERE NOT EXISTS (SELECT 1 FROM read_parquet('data/customers.parquet') c WHERE c.customer_id = t.customer_id)) AS orphan_txn_customers
),
anomaly_check AS (
    SELECT
        'Business Rule Audit' AS audit_category,
        (SELECT COUNT(*) FROM read_parquet('data/transactions.parquet') WHERE amount <= 0) AS invalid_amounts,
        (SELECT COUNT(*) FROM (SELECT event_id, COUNT(*) FROM read_parquet('data/events.parquet') GROUP BY event_id HAVING COUNT(*) > 1)) AS duplicate_event_ids
)
SELECT * FROM null_check
UNION ALL
SELECT audit_category, orphan_event_customers, orphan_txn_customers, 0 FROM orphan_check
UNION ALL
SELECT audit_category, invalid_amounts, duplicate_event_ids, 0 FROM anomaly_check;
