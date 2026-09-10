# amazon_ads_dbt — Analytics Engineering layer (dbt + BigQuery)

This is the dbt project for the Amazon Ads warehouse. It's the same four
Amazon report sources as the root [`README`](../README.md), modeled with a
conventional staging → marts pattern and running against **BigQuery**
(project `amazon-ads-mmm`, dataset `amazon_ads_warehouse`), instead of the
SQLite prototype in the repo root.

## Layers

**staging/** — one model per raw source, 1:1 with the source table. Only
column renames (raw Amazon column headers → snake_case) and light type
casting. No business logic.

| Model | Source |
|---|---|
| `stg_bulk_campaigns` | `raw_bulk_campaigns` — campaign structure (Portfolios/Campaigns/Ad Groups/Keywords) |
| `stg_advertised_products` | `raw_advertised_products` — per-ASIN ad performance |
| `stg_search_terms` | `raw_search_terms` — search query performance |
| `stg_business_report` | `raw_business_report` — organic + ad sales per ASIN |

**marts/** — the star schema. Three dimensions, three daily/snapshot facts,
and one weekly rollup:

| Model | Grain | Notes |
|---|---|---|
| `dim_date` | one row per day, 2025-01-01 to 2026-12-31 | built with `dbt_utils.date_spine` |
| `dim_campaign` | one row per `campaign_id` | deduplicated from the bulk file; also carries `ad_product` (SP/SB/SD) |
| `dim_product` | one row per `sku` | deduplicated from the bulk file |
| `fact_ads_daily` | date x campaign x ASIN | from `stg_advertised_products` |
| `fact_search_term` | date x campaign x search term x match type | from `stg_search_terms` |
| `fact_business_report` | one row per parent ASIN | organic + ad sales snapshot |
| `fact_weekly_channel_performance` | week x ad_product | `fact_ads_daily` joined to `dim_campaign` for the channel, rolled up weekly |

Everything is `+materialized: view` (see `dbt_project.yml`) — fine at this
data volume; `fact_weekly_channel_performance` is the first candidate for
`table` or `incremental` once this runs on a real report cadence instead of
ad-hoc loads.

## Data tests

Every model has `not_null`/`unique` on its grain, `relationships` tests
tying each fact's `campaign_name`/`asin` back to `dim_campaign`/`dim_product`,
and `dbt_utils.unique_combination_of_columns` grain checks on
`fact_ads_daily` and `fact_weekly_channel_performance`. Run them with `dbt test`
(see below). Full list in `models/marts/schema.yml`.

## How to run

```bash
cd amazon_ads_dbt
dbt deps          # installs dbt_utils (see packages.yml)
dbt build         # runs models + tests
dbt docs generate && dbt docs serve   # lineage graph + column docs, browsable
```

Requires a BigQuery service account with access to `amazon-ads-mmm` and a
`profiles.yml` pointing at it (not committed — see `.gitignore`).

## Why this exists next to the SQLite version

The root of the repo has a SQLite prototype of the same warehouse feeding a
Marketing Mix Model. This dbt project is the migration of that warehouse to
a real cloud stack (BigQuery) with the testing/docs/staging-marts discipline
a production analytics team would expect — it's the piece to look at for
Analytics Engineering specifically; the MMM notebooks are downstream of the
SQLite version, not this one (yet — porting the MMM prep to read from
BigQuery instead is the natural next step).
