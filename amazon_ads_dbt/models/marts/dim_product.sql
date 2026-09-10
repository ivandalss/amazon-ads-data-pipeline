with campaigns as (

    select * from {{ ref('stg_bulk_campaigns') }}

),

deduplicated as (

    select
        sku,
        asin,
        row_number() over (
            partition by sku
            -- NULLS LAST - see dim_campaign.sql for why this matters:
            -- without it, a row with a null ASIN can win the dedup over
            -- a row that has the real one.
            order by asin nulls last
        ) as rn

    from campaigns
    where sku is not null

),

final as (

    select
        sku,
        asin

    from deduplicated
    where rn = 1

)

select * from final
