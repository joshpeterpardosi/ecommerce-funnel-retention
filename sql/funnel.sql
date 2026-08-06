WITH stage_counts AS (
    SELECT
        device,
        event_type,
        COUNT(DISTINCT customer_id) AS unique_users,
        CASE event_type
            WHEN 'page_view' THEN 1
            WHEN 'product_view' THEN 2
            WHEN 'add_to_cart' THEN 3
            WHEN 'checkout_start' THEN 4
            WHEN 'purchase' THEN 5
            ELSE 99
        END AS stage_order
    FROM read_parquet('data/events.parquet')
    WHERE event_type IN ('page_view', 'product_view', 'add_to_cart', 'checkout_start', 'purchase')
    GROUP BY device, event_type
),
funnel_window AS (
    SELECT
        device,
        stage_order,
        event_type AS funnel_stage,
        unique_users,
        FIRST_VALUE(unique_users) OVER (PARTITION BY device ORDER BY stage_order) AS top_stage_users,
        LAG(unique_users) OVER (PARTITION BY device ORDER BY stage_order) AS prev_stage_users
    FROM stage_counts
)
SELECT
    device,
    stage_order,
    funnel_stage,
    unique_users,
    ROUND((unique_users * 100.0) / top_stage_users, 2) AS overall_conversion_pct,
    ROUND((unique_users * 100.0) / COALESCE(prev_stage_users, unique_users), 2) AS step_conversion_pct,
    ROUND(100.0 - ((unique_users * 100.0) / COALESCE(prev_stage_users, unique_users)), 2) AS dropoff_pct
FROM funnel_window
ORDER BY device, stage_order;
