-- =============================================================================
-- Query 5 — Daily spend and ROAS trend with rolling 7-day average
-- =============================================================================
-- Business question: is blended portfolio performance trending up, down, or
-- stable? Where are the inflection points worth investigating?
--
-- Output: daily totals + 7-day rolling spend and ROAS, plus a flag for days
-- whose ROAS deviates more than 50% from its rolling value.
--
-- DATA CAVEAT: the sample reports are one-month (Feb 2025) *summary* exports,
-- not daily breakdowns. Each fact row is a period total keyed on its first
-- active date, so on this sample the "daily" series is really "spend by start
-- date" and the trend/anomaly flags are not meaningful. The query is kept as
-- the monitoring pattern to run once the reports are pulled with a daily time
-- unit.
--
-- Rolling ROAS is computed as a ratio of rolling sums (sum of sales / sum of
-- spend over the window), not as an average of daily ratios, so low-spend days
-- don't get the same weight as high-spend days.
-- =============================================================================

WITH daily AS (
    SELECT
        date_id,
        SUM(spend)    AS spend,
        SUM(sales_7d) AS sales,
        SUM(orders_7d) AS orders
    FROM fact_ads_daily
    GROUP BY date_id
),
with_rolling AS (
    SELECT
        date_id,
        ROUND(spend, 2) AS daily_spend,
        ROUND(sales, 2) AS daily_sales,
        orders          AS daily_orders,
        ROUND(sales * 1.0 / NULLIF(spend, 0), 2) AS daily_roas,
        ROUND(AVG(spend) OVER (
            ORDER BY date_id
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 2) AS rolling_7d_spend,
        ROUND(
            SUM(sales) OVER (ORDER BY date_id ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) * 1.0
            / NULLIF(SUM(spend) OVER (ORDER BY date_id ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0),
        2) AS rolling_7d_roas,
        -- WoW change in spend
        LAG(spend, 7) OVER (ORDER BY date_id) AS spend_7d_ago
    FROM daily
)
SELECT
    date_id,
    daily_spend,
    rolling_7d_spend,
    daily_sales,
    daily_orders,
    daily_roas,
    rolling_7d_roas,
    ROUND(spend_7d_ago, 2) AS spend_one_week_ago,
    -- Week-over-week % change in spend
    ROUND(
        (daily_spend - spend_7d_ago) * 1.0 / NULLIF(spend_7d_ago, 0),
        4
    ) AS spend_wow_change,
    -- Flag days where ROAS deviates more than 50% from rolling avg
    CASE
        WHEN ABS(daily_roas - rolling_7d_roas) / NULLIF(rolling_7d_roas, 0) > 0.5
        THEN 'roas_anomaly'
        ELSE NULL
    END AS anomaly_flag
FROM with_rolling
ORDER BY date_id;
