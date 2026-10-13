-- One row per week: totals and trends for the dashboard.
select * from {{ ref('stg_mmm_weekly') }}
