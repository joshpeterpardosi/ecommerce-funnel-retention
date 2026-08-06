WITH max_date AS (
    SELECT MAX(transaction_timestamp) AS reference_date
    FROM read_parquet('data/transactions.parquet')
    WHERE status = 'Completed'
),
customer_rfm_raw AS (
    SELECT
        t.customer_id,
        DATEDIFF('day', MAX(t.transaction_timestamp), (SELECT reference_date FROM max_date)) AS recency_days,
        COUNT(t.transaction_id) AS frequency,
        SUM(t.amount) AS monetary
    FROM read_parquet('data/transactions.parquet') t
    WHERE t.status = 'Completed'
    GROUP BY t.customer_id
),
rfm_scores AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(4) OVER (ORDER BY frequency ASC) AS f_score,
        NTILE(4) OVER (ORDER BY monetary ASC) AS m_score
    FROM customer_rfm_raw
),
rfm_segmented AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        r_score,
        f_score,
        m_score,
        (r_score + f_score + m_score) AS total_rfm_score,
        CASE
            WHEN r_score = 4 AND f_score = 4 AND m_score = 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 3 AND f_score <= 2 THEN 'Promising / Recent'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
            ELSE 'Needs Attention / Churned'
        END AS rfm_segment
    FROM rfm_scores
)
SELECT
    rfm_segment,
    COUNT(customer_id) AS customer_count,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency), 1) AS avg_frequency,
    ROUND(AVG(monetary), 2) AS avg_monetary_spend,
    ROUND(SUM(monetary), 2) AS total_segment_revenue
FROM rfm_segmented
GROUP BY rfm_segment
ORDER BY total_segment_revenue DESC;
