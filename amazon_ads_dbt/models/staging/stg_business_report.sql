with source as (

    select * from {{ source('amazon_ads_raw', 'raw_business_report') }}

),

renamed as (

    select
        `_Parent_ ASIN`                as parent_asin,
        `Title`                        as product_title,
        `Sessions - Total`             as sessions_total,
        `Session Percentage - Total`   as session_pct_total,
        `Page Views - Total`           as page_views_total,
        `Page Views Percentage - Total` as page_views_pct_total,
        `Featured Offer _Buy Box_ Percentage` as buy_box_pct,
        `Units Ordered`                as units_ordered,
        `Unit Session Percentage`      as unit_session_pct,
        `Ordered Product Sales`        as ordered_product_sales,
        `Total Order Items`            as total_order_items

    from source

)

select * from renamed
