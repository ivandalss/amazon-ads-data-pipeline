with campaigns as (

    select * from {{ ref('stg_bulk_campaigns') }}

),

deduplicated as (

    select
        campaign_id,
        campaign_name,
        product as ad_product,
        targeting_type,
        state,
        daily_budget,
        bidding_strategy,
        row_number() over (
            partition by campaign_id
            -- NULLS LAST: without this, BigQuery's default NULL-first
            -- ascending order picks a row with a null campaign_name over
            -- a row that has the real name, whenever both exist for the
            -- same campaign_id (the bulk file has multiple entity-type
            -- rows - Campaign, Keyword, Product Ad, etc. - sharing a
            -- campaign_id, and not all of them carry the name).
            order by campaign_name nulls last
        ) as rn

    from campaigns
    where campaign_id is not null

),

final as (

    select
        campaign_id,
        campaign_name,
        ad_product,
        targeting_type,
        state,
        daily_budget,
        bidding_strategy

    from deduplicated
    where rn = 1

)

select * from final
