with ads_daily as (

    select * from {{ ref('fact_ads_daily') }}

),

campaigns as (

    select * from {{ ref('dim_campaign') }}

),

joined as (

    select
        date_trunc(ads_daily.date_id, week) as week,
        coalesce(campaigns.ad_product, 'unknown') as ad_product,
        ads_daily.spend,
        ads_daily.sales,
        ads_daily.clicks,
        ads_daily.orders

    from ads_daily
    left join campaigns
        on ads_daily.campaign_name = campaigns.campaign_name

),

aggregated as (

    select
        week,
        ad_product,
        sum(spend)   as total_spend,
        sum(sales)   as total_sales,
        sum(clicks)  as total_clicks,
        sum(orders)  as total_orders,
        safe_divide(sum(sales), nullif(sum(spend), 0)) as roas

    from joined
    group by
        week,
        ad_product

)

select * from aggregated
