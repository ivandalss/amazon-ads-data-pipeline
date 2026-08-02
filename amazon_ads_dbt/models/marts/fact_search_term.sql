with search_terms as (

    select * from {{ ref('stg_search_terms') }}

),

aggregated as (

    select
        start_date              as date_id,
        campaign_name,
        customer_search_term,
        match_type,
        sum(impressions)        as impressions,
        sum(clicks)              as clicks,
        sum(spend)               as spend,
        sum(total_sales_7d)      as sales,
        sum(total_orders_7d)     as orders,
        sum(total_units_7d)      as units

    from search_terms
    where start_date is not null
      and customer_search_term is not null

    group by
        start_date,
        campaign_name,
        customer_search_term,
        match_type

)

select * from aggregated
