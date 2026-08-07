WITH devices AS (
    SELECT DISTINCT device FROM read_parquet('data/events.parquet')
),
stages AS (
    SELECT 1 AS stage_order, 'page_view' AS funnel_stage
    UNION ALL SELECT 2, 'product_view'
    UNION ALL SELECT 3, 'add_to_cart'
    UNION ALL SELECT 4, 'checkout_start'
    UNION ALL SELECT 5, 'purchase'
),
device_stages AS (
    SELECT d.device, s.stage_order, s.funnel_stage
    FROM devices d
    CROSS JOIN stages s
),
pv AS (
    SELECT session_id, customer_id, device, MIN(timestamp) AS pv_time
    FROM read_parquet('data/events.parquet')
    WHERE event_type = 'page_view'
    GROUP BY session_id, customer_id, device
),
prod AS (
    SELECT e.session_id, e.customer_id, e.device, MIN(e.timestamp) AS prod_time
    FROM read_parquet('data/events.parquet') e
    JOIN pv ON e.session_id = pv.session_id AND e.timestamp >= pv.pv_time
    WHERE e.event_type = 'product_view'
    GROUP BY e.session_id, e.customer_id, e.device
),
cart AS (
    SELECT e.session_id, e.customer_id, e.device, MIN(e.timestamp) AS cart_time
    FROM read_parquet('data/events.parquet') e
    JOIN prod ON e.session_id = prod.session_id AND e.timestamp >= prod.prod_time
    WHERE e.event_type = 'add_to_cart'
    GROUP BY e.session_id, e.customer_id, e.device
),
chk AS (
    SELECT e.session_id, e.customer_id, e.device, MIN(e.timestamp) AS chk_time
    FROM read_parquet('data/events.parquet') e
    JOIN cart ON e.session_id = cart.session_id AND e.timestamp >= cart.cart_time
    WHERE e.event_type = 'checkout_start'
    GROUP BY e.session_id, e.customer_id, e.device
),
pur AS (
    SELECT e.session_id, e.customer_id, e.device, MIN(e.timestamp) AS pur_time
    FROM read_parquet('data/events.parquet') e
    JOIN chk ON e.session_id = chk.session_id AND e.timestamp >= chk.chk_time
    WHERE e.event_type = 'purchase'
    GROUP BY e.session_id, e.customer_id, e.device
),
stage_counts_raw AS (
    SELECT device, 1 AS stage_order, COUNT(DISTINCT customer_id) AS unique_users FROM pv GROUP BY device
    UNION ALL
    SELECT device, 2, COUNT(DISTINCT customer_id) FROM prod GROUP BY device
    UNION ALL
    SELECT device, 3, COUNT(DISTINCT customer_id) FROM cart GROUP BY device
    UNION ALL
    SELECT device, 4, COUNT(DISTINCT customer_id) FROM chk GROUP BY device
    UNION ALL
    SELECT device, 5, COUNT(DISTINCT customer_id) FROM pur GROUP BY device
),
stage_counts AS (
    SELECT
        ds.device,
        ds.stage_order,
        ds.funnel_stage,
        COALESCE(scr.unique_users, 0) AS unique_users
    FROM device_stages ds
    LEFT JOIN stage_counts_raw scr
        ON ds.device = scr.device AND ds.stage_order = scr.stage_order
),
funnel_window AS (
    SELECT
        device,
        stage_order,
        funnel_stage,
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
    ROUND((unique_users * 100.0) / NULLIF(top_stage_users, 0), 2) AS overall_conversion_pct,
    ROUND((unique_users * 100.0) / NULLIF(COALESCE(prev_stage_users, unique_users), 0), 2) AS step_conversion_pct,
    ROUND(100.0 - ((unique_users * 100.0) / NULLIF(COALESCE(prev_stage_users, unique_users), 0)), 2) AS dropoff_pct
FROM funnel_window
ORDER BY device, stage_order;
