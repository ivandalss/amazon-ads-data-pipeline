with date_spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2025-01-01' as date)",
        end_date="cast('2026-12-31' as date)"
    ) }}

),

renamed as (

    select
        date_day                          as date_id,
        date_day                          as full_date,
        extract(year from date_day)       as year,
        extract(month from date_day)      as month,
        extract(day from date_day)        as day,
        extract(quarter from date_day)    as quarter,
        extract(dayofweek from date_day)  as day_of_week,
        format_date('%A', date_day)       as day_name,
        format_date('%B', date_day)       as month_name

    from date_spine

)

select * from renamed
