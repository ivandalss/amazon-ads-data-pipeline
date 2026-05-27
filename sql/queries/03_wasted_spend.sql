-- =============================================================================
-- Query 3 — Wasted spend: search terms burning budget without converting
-- =============================================================================
-- Business question: which search terms are eating budget with high clicks
-- but zero or near-zero conversions? These are candidates for negative
-- keywords.
--
-- Definition of "wasted":
--   - 15+ clicks (statistical floor — small samples are noise)
--   - 0 orders OR ACoS > 100% (you spent more than you made)
--   - Ranked by total spend wasted, descending
--
-- Why this matters: this is the mirror of Q2. Both queries together drive
-- a typical "optimization sprint" — promote winners, kill losers.
-- =============================================================================

WITH agg AS (
    SELECT
        st.customer_search_term,
        c.campaign_name,
        c.targeting_type,
        SUM(st.impressions) AS impressions,
        SUM(st.clicks)      AS clicks,
        SUM(st.spend)       AS spend,
        SUM(st.sales_7d)    AS sales,
        SUM(st.orders_7d)   AS orders
    FROM fact_search_term st
    JOIN dim_campaign c USING (campaign_id)
    GROUP BY st.customer_search_term, c.campaign_name, c.targeting_type
),
flagged AS (
    SELECT
        customer_search_term,
        campaign_name,
        targeting_type,
        clicks,
        ROUND(spend, 2) AS spend,
        ROUND(sales, 2) AS sales,
        orders,
        ROUND(spend * 1.0 / NULLIF(sales, 0), 4) AS acos,
        CASE
            WHEN orders = 0                       THEN 'no_conversions'
            WHEN spend > sales                    THEN 'unprofitable'
            ELSE 'review'
        END AS waste_reason
    FROM agg
    WHERE clicks >= 15
      AND (orders = 0 OR spend > sales)
)
SELECT
    waste_reason,
    customer_search_term,
    campaign_name,
    targeting_type,
    clicks,
    spend,
    sales,
    orders,
    acos
FROM flagged
ORDER BY spend DESC
LIMIT 50;
