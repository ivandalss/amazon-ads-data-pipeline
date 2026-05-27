-- =============================================================================
-- Query 1 — Campaign ROAS with total-business context (TACoS)
-- =============================================================================
-- Business question: which campaigns are most efficient on their own ROAS,
-- AND how do they look when we put their spend against TOTAL business sales
-- (the TACoS lens)?
--
-- Why this matters: a campaign with great ROAS in isolation can still be a
-- small fraction of total business sales. TACoS (Total ACoS = ad spend /
-- total sales) is the metric that matters for portfolio decisions.
-- =============================================================================

WITH campaign_perf AS (
    -- Aggregate ad performance per campaign (joining facts + dim_campaign)
    SELECT
        c.campaign_id,
        c.campaign_name,
        c.portfolio_name,
        c.targeting_type,
        SUM(f.spend)     AS total_spend,
        SUM(f.sales_7d)  AS total_ad_sales,
        SUM(f.orders_7d) AS total_orders
    FROM fact_ads_daily f
    JOIN dim_campaign c USING (campaign_id)
    GROUP BY c.campaign_id, c.campaign_name, c.portfolio_name, c.targeting_type
),
business_total AS (
    -- Total business sales (ads + organic), summed across all ASINs
    SELECT SUM(ordered_product_sales) AS total_business_sales
    FROM fact_business_report
),
final AS (
    SELECT
        cp.campaign_name,
        cp.portfolio_name,
        cp.targeting_type,
        ROUND(cp.total_spend, 2)     AS spend,
        ROUND(cp.total_ad_sales, 2)  AS ad_sales,
        cp.total_orders              AS orders,
        -- ROAS = ad sales / ad spend  (channel-level efficiency)
        ROUND(cp.total_ad_sales * 1.0 / NULLIF(cp.total_spend, 0), 2) AS roas,
        -- ACoS = ad spend / ad sales  (inverse of ROAS, marketer convention)
        ROUND(cp.total_spend * 1.0 / NULLIF(cp.total_ad_sales, 0), 4) AS acos,
        -- TACoS = ad spend / TOTAL business sales (portfolio efficiency)
        ROUND(cp.total_spend * 1.0 / NULLIF(bt.total_business_sales, 0), 4) AS tacos
    FROM campaign_perf cp
    CROSS JOIN business_total bt
)
SELECT *
FROM final
WHERE spend > 0
ORDER BY roas DESC;
