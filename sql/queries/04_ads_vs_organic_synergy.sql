-- =============================================================================
-- Query 4 — Ads vs organic synergy at the ASIN level
-- =============================================================================
-- Business question: for each product, what fraction of total sales comes
-- from ads vs organic? Where are we over-relying on ads (high ad share),
-- and where are ads driving the organic engine?
--
-- This is the foundational view for marketing-mix thinking applied to
-- Amazon: every product has a different healthy ad-share, and the goal
-- is to find products where ads are still incremental rather than
-- displacing organic.
-- =============================================================================

WITH ad_sales_per_asin AS (
    -- Sum of advertised-product sales per ASIN (across all campaigns)
    SELECT
        asin,
        SUM(spend)    AS ad_spend,
        SUM(sales_7d) AS ad_sales
    FROM fact_ads_daily
    WHERE asin IS NOT NULL
    GROUP BY asin
),
total_sales_per_asin AS (
    -- Total sales from Business Report (ads + organic)
    SELECT
        asin,
        SUM(ordered_product_sales) AS total_sales,
        SUM(sessions_total)        AS sessions,
        AVG(unit_session_pct)      AS avg_conversion
    FROM fact_business_report
    GROUP BY asin
),
combined AS (
    SELECT
        t.asin,
        p.title,
        ROUND(t.total_sales, 2) AS total_sales,
        ROUND(COALESCE(a.ad_sales, 0), 2) AS ad_sales,
        ROUND(t.total_sales - COALESCE(a.ad_sales, 0), 2) AS organic_sales,
        ROUND(COALESCE(a.ad_spend, 0), 2) AS ad_spend,
        t.sessions,
        ROUND(t.avg_conversion, 2) AS avg_conversion_pct,
        -- Share of sales that came from ads (lower is healthier in general)
        ROUND(COALESCE(a.ad_sales, 0) * 1.0 / NULLIF(t.total_sales, 0), 4) AS ad_sales_share,
        -- TACoS at the ASIN level
        ROUND(COALESCE(a.ad_spend, 0) * 1.0 / NULLIF(t.total_sales, 0), 4) AS tacos_asin
    FROM total_sales_per_asin t
    LEFT JOIN ad_sales_per_asin a USING (asin)
    LEFT JOIN dim_product p USING (asin)
    WHERE t.total_sales > 0
)
SELECT
    asin,
    SUBSTR(title, 1, 60) AS title_short,
    total_sales,
    ad_sales,
    organic_sales,
    ad_spend,
    sessions,
    avg_conversion_pct,
    ad_sales_share,
    tacos_asin,
    CASE
        WHEN ad_sales_share >= 0.80 THEN 'ad_dependent'
        WHEN ad_sales_share >= 0.40 THEN 'balanced'
        WHEN ad_sales_share >  0    THEN 'organic_strong'
        ELSE 'no_ads'
    END AS health_label
FROM combined
ORDER BY total_sales DESC;
