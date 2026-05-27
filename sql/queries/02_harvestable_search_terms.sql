-- =============================================================================
-- Query 2 — Harvestable search terms (auto/broad → exact)
-- =============================================================================
-- Business question: which customer search terms in our Auto and Broad
-- campaigns have already converted profitably? These are candidates to
-- "harvest" into Exact match campaigns where we can bid more efficiently.
--
-- Rules used:
--   - At least 2 orders attributed to that search term
--   - ACoS below 30% (profitable threshold; tune per business margin)
--   - Search term is not already the exact campaign target (avoid duplicates)
--
-- Why this matters: harvesting is one of the most common, highest-ROI
-- actions in Amazon Ads management. Automating this with SQL replaces
-- hours of manual analysis per account.
-- =============================================================================

WITH search_term_perf AS (
    SELECT
        st.customer_search_term,
        c.campaign_name,
        c.targeting_type,
        st.match_type,
        SUM(st.impressions) AS impressions,
        SUM(st.clicks)      AS clicks,
        SUM(st.spend)       AS spend,
        SUM(st.sales_7d)    AS sales,
        SUM(st.orders_7d)   AS orders
    FROM fact_search_term st
    JOIN dim_campaign c USING (campaign_id)
    WHERE c.targeting_type IN ('Auto', 'Manual')
      AND st.match_type IN ('BROAD', 'PHRASE')
    GROUP BY st.customer_search_term, c.campaign_name, c.targeting_type, st.match_type
),
ranked AS (
    SELECT
        customer_search_term,
        campaign_name,
        targeting_type,
        match_type,
        impressions,
        clicks,
        ROUND(spend, 2)  AS spend,
        ROUND(sales, 2)  AS sales,
        orders,
        ROUND(sales * 1.0 / NULLIF(spend, 0), 2) AS roas,
        ROUND(spend * 1.0 / NULLIF(sales, 0), 4) AS acos,
        ROUND(orders * 1.0 / NULLIF(clicks, 0), 4) AS conversion_rate,
        -- Rank within each source campaign by sales contribution
        ROW_NUMBER() OVER (
            PARTITION BY campaign_name
            ORDER BY sales DESC
        ) AS rank_in_campaign
    FROM search_term_perf
    WHERE orders >= 2
      AND spend > 0
)
SELECT *
FROM ranked
WHERE acos < 0.30      -- profitable threshold
  AND rank_in_campaign <= 5
ORDER BY campaign_name, rank_in_campaign;
