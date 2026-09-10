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
| `fact_ads_daily` | date x campaign x ASIN | from `stg_advertised_products`; designed as incremental, currently a plain table (see below) |
| `fact_search_term` | date x campaign x search term x match type | from `stg_search_terms` |
| `fact_business_report` | one row per parent ASIN | organic + ad sales snapshot |
| `fact_weekly_channel_performance` | week x ad_product | `fact_ads_daily` joined to `dim_campaign` for the channel, rolled up weekly |

Everything defaults to `+materialized: view` (see `dbt_project.yml`), except
`fact_ads_daily`, which is `materialized='table'`.

`fact_ads_daily` is **designed** to be incremental — the reasoning is
written out at the top of `fact_ads_daily.sql`. The config that would
restore it, once billing is enabled on the project:

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={'field': 'date_id', 'data_type': 'date'},
    on_schema_change='sync_all_columns'
) }}

-- ... in the staging CTE:
{% if is_incremental() %}
where start_date >= date_sub(current_date(), interval 3 day)
{% endif %}
```

`insert_overwrite`, partitioned on `date_id`, with a 3-day lookback window
to reprocess only recently-arrived/corrected report rows instead of
rebuilding the whole table on every run. It's currently reverted to a
plain table because this project's BigQuery project has no billing account
attached: only the *first* build of a dbt incremental model is a plain
`CREATE TABLE AS SELECT` (allowed in the free-tier sandbox); every refresh
after that compiles to a `MERGE`/`INSERT` script, and BigQuery's sandbox
blocks all DML. Confirmed by actually running it, not guessed — see the
findings section below. Enabling billing on the project (BigQuery still
gives 1TB of query processing free/month) would unblock it; not worth doing
just for a portfolio demo.

`fact_weekly_channel_performance` is the next candidate for `table` or
`incremental` once this runs on a real report cadence instead of ad-hoc
loads.

## Data tests

Every model has `not_null`/`unique` on its grain, `relationships` tests
tying each fact's `campaign_name`/`asin` back to `dim_campaign`/`dim_product`,
and `dbt_utils.unique_combination_of_columns` grain checks on
`fact_ads_daily` and `fact_weekly_channel_performance`. Run them with `dbt test`
(see below). Full list in `models/marts/schema.yml`.

## Known data-quality findings (from adding the tests above)

Adding `relationships`/`not_null` tests to this project surfaced two real
bugs and two genuine (unfixable-by-code) data-modeling limitations.

**Bug 1 — `dim_campaign`/`dim_product` dedup picked the wrong row.**
`row_number() over (partition by campaign_id order by campaign_name)`
relied on BigQuery's default `ORDER BY` behavior, which sorts `NULL` first
ascending — so for campaign_ids where the bulk file has both a named row
and a null-name row (different entity types - Campaign, Keyword, Product
Ad, etc. - share a campaign_id but not all carry the name), the dedup was
silently picking the null-name row as the "winner." That broke 600
campaign names in `dim_campaign` and, downstream, 2706 rows in
`fact_search_term` that couldn't match on `campaign_name`. Fixed with an
explicit `NULLS LAST` in both `dim_campaign` and `dim_product` — verified
by rerunning: 2706 failures dropped to 3, and stayed at 3 after bug 2
(below) was also fixed. Those 3 are campaign names genuinely absent from
the bulk snapshot (report pull-time gap, same cause as the larger
`fact_ads_daily.campaign_name` gap noted further down) — small enough to
leave as a `warn`.

**Bug 2 — inconsistent ASIN/SKU anonymization broke joins across reports.**
`fact_ads_daily.asin` → `dim_product.asin` failed for ~100% of rows (1306
of ~1300). Root cause was in `src/anonymize.py`, not in the dbt models:
`process_bulk_file`'s id-hashing list named the column `"ASIN"`, but the
bulk file's real header is `"ASIN (Informational only)"` — the names
didn't match, so that column was silently never hashed and shipped with
the *real* ASIN, while `process_advertised_product` correctly hashed
`"Advertised ASIN"` to a placeholder. Same real product, two different
anonymized representations, zero overlap by construction. On top of that,
`hash_id()`'s placeholder prefix was derived from each column's own name
(`"Advertised ASIN"` → `Advertised_ASIN_...`), so even a correctly-hashed
ASIN wouldn't match the same ASIN hashed from a differently-named column
elsewhere. Fixed both: corrected the column name, and added
`CANONICAL_ID_PREFIXES` so ASIN/SKU always hash to the same prefix
regardless of source column. Verified directly against the raw files
(not guessed): before the fix, bulk vs. advertised-product ASINs had 45
unique values on each side and **0** overlap; after, still 45 and 45, with
**45/45** overlapping. Re-running `python src/anonymize.py` and reloading
`data/processed/*.csv` into BigQuery is required to pick this up — the
already-loaded `raw_*` tables in BigQuery still have the old, inconsistent
anonymization until that's done.

**Real limitation (not a bug) — `fact_business_report.parent_asin` vs.
`dim_product.asin`.** Even after fixing bug 2, most bulk-file ASINs don't
match a Business Report parent ASIN (51 of 66 rows fail the relationship
test after the anonymization fix). This confirms the original suspicion:
the Business Report is at *parent* ASIN grain, while `dim_product.asin` is
a child/variant ASIN from the bulk file — they're genuinely different
identifier spaces for a portion of the catalog, not something
anonymization or a dedup fix can close. Left as `severity: warn` with this
note rather than silently patched or hidden.

**Real limitation (not a bug) — `fact_ads_daily.campaign_name` gap.** 196
rows (182 distinct campaign names) in `fact_ads_daily` don't resolve
against `dim_campaign`. Checked directly against the raw data: every
campaign name in `dim_campaign` *is* present in the Advertised Product
report — the gap only goes one way. Those 182 names have real spend
spread evenly across the whole report month, but aren't in the current
bulk-file export, which reflects account structure *as configured today*.
Most likely explanation: campaigns paused/archived/deleted since the
report's date range, so they've dropped out of the current bulk snapshot
even though they generated spend at the time. Same root cause as the
smaller `fact_search_term` gap below, just larger here because the AP
report spans a full month. Set to `severity: warn`; closing it fully would
need a bulk-file pull from closer to the report's own date range, not a
code fix.

## How to run

```bash
cd amazon_ads_dbt
dbt deps          # installs dbt_utils (see packages.yml)
dbt build         # runs models + tests
dbt docs generate && dbt docs serve   # lineage graph + column docs, browsable
```

Requires a BigQuery service account with access to `amazon-ads-mmm` and a
`profiles.yml` pointing at it (not committed — see `.gitignore`).

## CI

`.github/workflows/dbt_ci.yml` runs `dbt build` (models + tests) on every
push to `amazon_ads_dbt/**`, and can also be triggered manually from the
Actions tab.

Auth uses **Workload Identity Federation**, not a service-account JSON key
— GitHub's OIDC token is exchanged for short-lived GCP credentials at run
time, so there's no long-lived secret to store, rotate, or leak. The
workflow impersonates `dbt-service-account@amazon-ads-mmm.iam.gserviceaccount.com`,
scoped so only workflows running from this exact repo
(`ivandalss/amazon-ads-data-pipeline`) can request that impersonation
(`--attribute-condition` on the identity pool provider). The service
account itself only holds `roles/bigquery.dataEditor` and
`roles/bigquery.jobUser` on the project — enough to build and test, nothing
broader.

Went with this over a JSON key because this project's org initially had
`iam.disableServiceAccountKeyCreation` enforced, which blocked key creation
entirely (see the git history for that dead end) — WIF sidesteps it
by never creating a key in the first place, which is also just the current
recommended pattern for CI → GCP auth regardless.

## Why this exists next to the SQLite version

The root of the repo has a SQLite prototype of the same warehouse feeding a
Marketing Mix Model. This dbt project is the migration of that warehouse to
a real cloud stack (BigQuery) with the testing/docs/staging-marts discipline
a production analytics team would expect — it's the piece to look at for
Analytics Engineering specifically; the MMM notebooks are downstream of the
SQLite version, not this one (yet — porting the MMM prep to read from
BigQuery instead is the natural next step).
