with source as (

    select * from {{ source('amazon_ads_raw', 'raw_bulk_campaigns') }}

),

renamed as (

    select
        `Product`                      as product,
        `Entity`                       as entity,
        `Campaign ID`                  as campaign_id,
        `Ad Group ID`                  as ad_group_id,
        `Portfolio ID`                 as portfolio_id,
        `Ad ID`                        as ad_id,
        `Keyword ID`                   as keyword_id,
        `Product Targeting ID`         as product_targeting_id,
        `Campaign Name`                as campaign_name,
        `Ad Group Name`                as ad_group_name,
        `Targeting Type`               as targeting_type,
        `State`                        as state,
        `Daily Budget`                 as daily_budget,
        `SKU`                          as sku,
        `ASIN _Informational only_`    as asin,
        `Ad Group Default Bid`         as ad_group_default_bid,
        `Bid`                          as bid,
        `Keyword Text`                 as keyword_text,
        `Match Type`                   as match_type,
        `Bidding Strategy`             as bidding_strategy,
        `Placement`                    as placement,
        `Percentage`                   as percentage,
        `Product Targeting Expression` as product_targeting_expression,
        `Impressions`                  as impressions,
        `Clicks`                       as clicks,
        `Click-through Rate`           as ctr,
        `Spend`                        as spend,
        `Sales`                        as sales,
        `Orders`                       as orders,
        `Units`                        as units,
        `Conversion Rate`              as conversion_rate,
        `ACOS`                         as acos,
        `CPC`                          as cpc,
        `ROAS`                         as roas

    from source

)

select * from renamed
