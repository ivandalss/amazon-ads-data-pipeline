-- Simulated data (see sources_mmm.yml). Row-level ratios (roas, tacos, ctr) are dropped on purpose:
-- they must be computed as ratios of sums in the BI layer, never averaged across rows.
select
    cast(week_start as date) as week_start,
    spend_sp,
    spend_sb,
    spend_dsp,
    spend_total,
    impressions_total,
    clicks_total,
    ad_sales,
    ad_orders,
    total_sales,
    organic_sales
from {{ source('mmm_synthetic', 'weekly_synthetic') }}
