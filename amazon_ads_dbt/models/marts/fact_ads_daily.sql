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
