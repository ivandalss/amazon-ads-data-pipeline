with source as (

    select * from {{ source('amazon_ads_raw', 'raw_search_terms') }}

),

renamed as (

    select
        `Start Date`                                as start_date,
        `End Date`                                   as end_date,
        `Portfolio name`                             as portfolio_name,
        `Campaign Name`                               as campaign_name,
        `Ad Group Name`                               as ad_group_name,
        `Targeting`                                   as targeting,
        `Match Type`                                  as match_type,
        `Customer Search Term`                        as customer_search_term,
        `Impressions`                                 as impressions,
        `Clicks`                                      as clicks,
        `Click-Thru Rate _CTR_`                       as ctr,
        `Cost Per Click _CPC_`                        as cpc,
        `Spend`                                       as spend,
        `7 Day Total Sales `                          as total_sales_7d,
        `Total Advertising Cost of Sales _ACOS_ `      as acos,
        `Total Return on Advertising Spend _ROAS_`     as roas,
        `7 Day Total Orders _#_`                       as total_orders_7d,
        `7 Day Total Units _#_`                        as total_units_7d,
        `7 Day Conversion Rate`                        as conversion_rate_7d

    from source

)

select * from renamed
