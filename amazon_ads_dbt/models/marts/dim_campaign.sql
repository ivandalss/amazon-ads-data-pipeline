with campaigns as (

    select * from {{ ref('stg_bulk_campaigns') }}

),

deduplicated as (

    select
        campaign_id,
        campaign_name,
        targeting_type,
        state,
        daily_budget,
        bidding_strategy,
        row_number() over (
            partition by campaign_id
            order by campaign_name
        ) as rn

    from campaigns
    where campaign_id is not null

),

final as (

    select
        campaign_id,
        campaign_name,
        targeting_type,
        state,
        daily_budget,
        bidding_strategy

    from deduplicated
    where rn = 1

)

select * from final
