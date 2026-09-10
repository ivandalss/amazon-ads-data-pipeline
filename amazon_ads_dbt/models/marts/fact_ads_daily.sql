-- Designed to run as an incremental model: materialized='incremental',
-- incremental_strategy='insert_overwrite', partitioned on date_id, with a
-- 3-day lookback (is_incremental() filtering to
-- start_date >= date_sub(current_date(), interval 3 day)) to absorb
-- late-arriving/corrected report rows without a full rebuild.
--
-- Reverted to a plain table here: this project's BigQuery project runs in
-- the free-tier sandbox with no billing account attached, and BigQuery's
-- sandbox mode blocks DML - which is exactly what the incremental run path
-- needs (only the *first* build of an incremental model is a plain CREATE
-- TABLE AS SELECT; every refresh after that is a MERGE/INSERT script).
-- Confirmed by actually running it: first build succeeded, the incremental
-- refresh failed with "Billing has not been enabled for this project...
-- DML queries are not allowed in the free tier." See
-- amazon_ads_dbt/README.md for the full writeup, including the exact
-- config that would restore incremental behavior on a billing-enabled
-- project.

{{ config(materialized='table') }}

with advertised_products as (

    select * from {{ ref('stg_advertised_products') }}

),

aggregated as (

    select
        start_date          as date_id,
        campaign_name,
        advertised_asin      as asin,
        advertised_sku       as sku,
        sum(impressions)     as impressions,
        sum(clicks)          as clicks,
        sum(spend)           as spend,
        sum(total_sales_7d)  as sales,
        sum(total_orders_7d) as orders,
        sum(total_units_7d)  as units

    from advertised_products
    where start_date is not null
      and advertised_asin is not null

    group by
        start_date,
        campaign_name,
        advertised_asin,
        advertised_sku

)

select * from aggregated
