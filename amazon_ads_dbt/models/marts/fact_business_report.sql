with business_report as (

    select * from {{ ref('stg_business_report') }}

),

final as (

    select
        parent_asin,
        product_title,
        sessions_total,
        session_pct_total,
        page_views_total,
        page_views_pct_total,
        buy_box_pct,
        units_ordered,
        unit_session_pct,
        ordered_product_sales as sales,
        total_order_items     as orders

    from business_report
    where parent_asin is not null

)

select * from final
