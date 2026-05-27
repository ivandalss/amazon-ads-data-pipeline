# Amazon Ads Analytics — SQL Warehouse from Marketplace Reports

A small data engineering project that takes raw Amazon Advertising reports
(in Excel), anonymizes them, models them into a star-schema SQL warehouse,
and runs analytical queries to answer real business questions: where to
harvest profitable keywords, where to cut wasted spend, how ads and organic
sales interact at the product level.

## Architecture

![architecture](docs/architecture.svg)

| Stage | Language | Module |
|-------|----------|--------|
| 1. Read raw .xlsx reports                | Python (pandas) | `src/anonymize.py` |
| 2. Strip brand names, hash IDs, write CSV | Python          | `src/anonymize.py` |
| 3. Transform to schema-shaped tables      | Python          | `src/load.py`      |
| 4. Define warehouse schema                | SQL (DDL)       | `sql/01_schema.sql`|
| 5. Load tables into SQLite                | Python + SQL    | `src/load.py`      |
| 6. Analytical queries                     | SQL             | `sql/queries/*.sql`|
| 7. Notebook narrative & charts            | Python (pandas, matplotlib) | `notebooks/analysis.ipynb` |

## Data sources

Four Amazon report types feed the warehouse:

- **Bulk file** — the master campaign structure (Portfolios, Campaigns, Ad Groups, Keywords, Product Ads). Multi-sheet Excel.
- **Search Term Report** — every customer search query that triggered an ad, with performance.
- **Advertised Product Report** — per-ASIN ad performance.
- **Business Report** — total sales (ads + organic) at the ASIN level. The piece that lets us compute TACoS.

Raw files are **not** committed (they contain identifiable brand data even
after anonymization). The anonymized CSVs in `data/processed/` are safe
to commit and reproduce the warehouse.

## Schema

A star schema with three fact tables (different grains) and three shared
dimensions:

- `dim_date`, `dim_campaign`, `dim_product`
- `fact_ads_daily`  — date × campaign × ASIN grain
- `fact_search_term` — date × campaign × search-query grain
- `fact_business_report` — snapshot × ASIN grain (ads + organic sales)

Schema is defined in `sql/01_schema.sql` and is dialect-agnostic
(developed on SQLite, will run on PostgreSQL or any analytical engine).

## Analytical queries

Each query in `sql/queries/` answers a concrete business question. They
demonstrate JOINs across facts and dimensions, CTEs for staged logic,
window functions (`ROW_NUMBER`, `LAG`, rolling averages), and conditional
aggregation.

| File | Question | Techniques |
|------|----------|------------|
| `01_campaign_roas_tacos.sql`     | Which campaigns are most efficient on their own ROAS — and how do they look against total business sales (TACoS)? | CTEs, cross-join, aggregation |
| `02_harvestable_search_terms.sql` | Which broad/auto search terms have converted profitably and should be promoted to exact-match campaigns? | `ROW_NUMBER`, partitioned ranking |
| `03_wasted_spend.sql`             | Which search terms are burning budget without converting? Candidates for negative keywords. | Conditional logic, filtering on aggregates |
| `04_ads_vs_organic_synergy.sql`   | For each product: what share of sales is from ads vs organic? Where is ad dependency too high? | Multi-fact join, label classification |
| `05_daily_trend_anomalies.sql`    | Daily spend and ROAS trend with rolling 7-day average and anomaly flags. | `LAG`, window functions, rolling averages |

## How to run

Prerequisites: Python 3.11+, `pip install -r requirements.txt`.

```bash
# 1. Place raw .xlsx files in data/raw/  (filenames as in /raw/.gitkeep)
# 2. Anonymize:
python src/anonymize.py
# 3. Build warehouse:
python src/load.py
# 4. Open notebooks/analysis.ipynb and run all cells.
```

End-to-end runtime on the sample dataset: ~10 seconds.

## What this project demonstrates

- **ETL fundamentals:** multi-source ingestion, schema design, idempotent
  loads, separation of raw / processed / warehouse layers.
- **SQL fluency:** CTEs, window functions, multi-fact joins, conditional
  aggregations across a real star schema.
- **Data-quality awareness:** anonymization layer, deterministic ID
  hashing (joins still work), documented mismatches (e.g., Parent vs
  Child ASIN coverage between facts).
- **Marketing measurement thinking:** the SQL questions are real
  questions from agency life — TACoS vs ACoS, harvesting, negative
  keywords, ads-vs-organic synergy.

## What's intentionally not in scope (and why)

- No orchestration tool (Airflow/Prefect): two scripts run in order is
  fine for a 4-source pipeline. In production, this would be a DAG.
- No managed warehouse (Snowflake/BigQuery): SQLite makes the project
  reproducible without cloud credentials. Schema and queries are
  portable.
- No streaming: marketplace reports are batch by nature.
- No marketing-mix modeling: that's a separate project on top of this
  warehouse. This project ends at "data is queryable"; the MMM lives
  downstream.

## File structure

```
.
├── README.md
├── requirements.txt
├── docs/
│   └── architecture.svg
├── src/
│   ├── anonymize.py
│   └── load.py
├── sql/
│   ├── 01_schema.sql
│   └── queries/
│       ├── 01_campaign_roas_tacos.sql
│       ├── 02_harvestable_search_terms.sql
│       ├── 03_wasted_spend.sql
│       ├── 04_ads_vs_organic_synergy.sql
│       └── 05_daily_trend_anomalies.sql
├── notebooks/
│   └── analysis.ipynb
└── data/
    ├── raw/           # .gitignored — contains identifiable .xlsx
    ├── processed/     # safe to commit — anonymized .csv
    └── warehouse.db   # .gitignored — rebuild with `python src/load.py`
```
