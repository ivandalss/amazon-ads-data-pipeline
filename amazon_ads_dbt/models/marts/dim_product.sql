with campaigns as (

    select * from {{ ref('stg_bulk_campaigns') }}

),

deduplicated as (

    select
        sku,
        asin,
        row_number() over (
            partition by sku
            order by asin
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
