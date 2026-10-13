-- Long format (one row per week x channel) so the BI layer can break spend down by channel.
with base as (
    select week_start, spend_sp, spend_sb, spend_dsp
    from {{ ref('stg_mmm_weekly') }}
)

select week_start, 'Sponsored Products' as channel, spend_sp as spend from base
union all
select week_start, 'Sponsored Brands' as channel, spend_sb as spend from base
union all
select week_start, 'DSP' as channel, spend_dsp as spend from base
