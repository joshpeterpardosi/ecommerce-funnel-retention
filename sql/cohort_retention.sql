WITH first_activity AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(timestamp)) AS cohort_month
    FROM read_parquet('data/events.parquet')
    GROUP BY customer_id
),
monthly_activity AS (
    SELECT DISTINCT
        e.customer_id,
        fa.cohort_month,
        DATE_TRUNC('month', e.timestamp) AS activity_month
    FROM read_parquet('data/events.parquet') e
    JOIN first_activity fa ON e.customer_id = fa.customer_id
),
cohort_sizes AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id) AS initial_cohort_size
    FROM first_activity
    GROUP BY cohort_month
),
retention_counts AS (
    SELECT
        ma.cohort_month,
        (DATEDIFF('month', ma.cohort_month, ma.activity_month)) AS period_offset,
        COUNT(DISTINCT ma.customer_id) AS active_users
    FROM monthly_activity ma
    GROUP BY ma.cohort_month, ma.activity_month
)
SELECT
    rc.cohort_month,
    cs.initial_cohort_size,
    rc.period_offset,
    rc.active_users,
    ROUND((rc.active_users * 100.0) / cs.initial_cohort_size, 2) AS retention_rate_pct
FROM retention_counts rc
JOIN cohort_sizes cs ON rc.cohort_month = cs.cohort_month
ORDER BY rc.cohort_month, rc.period_offset;
