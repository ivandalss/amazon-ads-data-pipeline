"""
ETL loader.

Reads anonymized CSVs from data/processed/, transforms them into the star
schema (dim_date, dim_campaign, dim_product, three fact tables), and loads
them into a SQLite database (data/warehouse.db).

Typical run: ~5-10 seconds on the sample dataset.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


HERE = Path(__file__).resolve().parent.parent
PROCESSED = HERE / "data" / "processed"
DB_PATH = HERE / "data" / "warehouse.db"
SCHEMA_SQL = HERE / "sql" / "01_schema.sql"


def _read_processed(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / name)


def _build_dim_date(*date_series: pd.Series) -> pd.DataFrame:
    """Build dim_date from all date columns observed in the facts."""
    all_dates = pd.concat([pd.to_datetime(s, errors="coerce") for s in date_series])
    all_dates = all_dates.dropna().drop_duplicates().sort_values()
    df = pd.DataFrame({"date_id": all_dates})
    df["year"] = df["date_id"].dt.year
    df["month"] = df["date_id"].dt.month
    df["week"] = df["date_id"].dt.isocalendar().week
    df["day_of_week"] = df["date_id"].dt.dayofweek + 1  # 1=Mon
    df["is_weekend"] = (df["day_of_week"] >= 6).astype(int)
    df["date_id"] = df["date_id"].dt.date
    return df


def _build_dim_campaign(bulk: pd.DataFrame) -> pd.DataFrame:
    """Extract one row per campaign from the bulk file's Campaign entities."""
    camp = bulk[bulk["Entity"] == "Campaign"].copy()
    df = pd.DataFrame({
        "campaign_id": camp["Campaign ID"],
        "campaign_name": camp["Campaign Name"],
        "portfolio_id": camp["Portfolio ID"],
        "portfolio_name": camp["Portfolio Name (Informational only)"],
        "targeting_type": camp["Targeting Type"],
        "bidding_strategy": camp["Bidding Strategy"],
        "state": camp["State"],
        "daily_budget": pd.to_numeric(camp["Daily Budget"], errors="coerce"),
    })
    return df.drop_duplicates(subset="campaign_id").dropna(subset=["campaign_id"])


def _build_dim_product(ap: pd.DataFrame, br: pd.DataFrame) -> pd.DataFrame:
    """Build dim_product from Advertised Product (asin+sku) and Business
    Report (asin+title)."""
    p1 = ap[["Advertised ASIN", "Advertised SKU"]].rename(
        columns={"Advertised ASIN": "asin", "Advertised SKU": "sku"}
    )
    p2 = br[["(Parent) ASIN", "Title"]].rename(
        columns={"(Parent) ASIN": "asin", "Title": "title"}
    )
    df = p1.merge(p2, on="asin", how="outer").drop_duplicates(subset="asin")
    return df.dropna(subset=["asin"])


def _build_fact_ads_daily(ap: pd.DataFrame, bulk: pd.DataFrame) -> pd.DataFrame:
    """Join Advertised Product report with campaign IDs from bulk on campaign name."""
    # Get campaign_id <-> campaign_name mapping from bulk
    camp = bulk[bulk["Entity"] == "Campaign"][["Campaign Name", "Campaign ID"]]
    camp = camp.drop_duplicates(subset="Campaign Name")

    df = ap.merge(camp, left_on="Campaign Name", right_on="Campaign Name", how="left")

    out = pd.DataFrame({
        "date_id": pd.to_datetime(df["Start Date"], errors="coerce").dt.date,
        "campaign_id": df["Campaign ID"],
        "asin": df["Advertised ASIN"],
        "sku": df["Advertised SKU"],
        "impressions": pd.to_numeric(df["Impressions"], errors="coerce").fillna(0).astype(int),
        "clicks": pd.to_numeric(df["Clicks"], errors="coerce").fillna(0).astype(int),
        "spend": pd.to_numeric(df["Spend"], errors="coerce").fillna(0.0),
        "sales_7d": pd.to_numeric(df["7 Day Total Sales "], errors="coerce").fillna(0.0),
        "orders_7d": pd.to_numeric(df["7 Day Total Orders (#)"], errors="coerce").fillna(0).astype(int),
        "units_7d": pd.to_numeric(df["7 Day Total Units (#)"], errors="coerce").fillna(0).astype(int),
        "advertised_sku_sales_7d": pd.to_numeric(df["7 Day Advertised SKU Sales "], errors="coerce").fillna(0.0),
        "other_sku_sales_7d": pd.to_numeric(df["7 Day Other SKU Sales "], errors="coerce").fillna(0.0),
    }).dropna(subset=["campaign_id"])

    # Aggregate to the schema's grain (date_id, campaign_id, asin) — raw data
    # may include multiple ad_groups per (date, campaign, asin) which we sum.
    return out.groupby(
        ["date_id", "campaign_id", "asin", "sku"], dropna=False, as_index=False
    ).agg({
        "impressions": "sum",
        "clicks": "sum",
        "spend": "sum",
        "sales_7d": "sum",
        "orders_7d": "sum",
        "units_7d": "sum",
        "advertised_sku_sales_7d": "sum",
        "other_sku_sales_7d": "sum",
    })


def _build_fact_search_term(st: pd.DataFrame, bulk: pd.DataFrame) -> pd.DataFrame:
    camp = bulk[bulk["Entity"] == "Campaign"][["Campaign Name", "Campaign ID"]]
    camp = camp.drop_duplicates(subset="Campaign Name")
    df = st.merge(camp, left_on="Campaign Name", right_on="Campaign Name", how="left")

    return pd.DataFrame({
        "date_id": pd.to_datetime(df["Start Date"], errors="coerce").dt.date,
        "campaign_id": df["Campaign ID"],
        "customer_search_term": df["Customer Search Term"],
        "targeting": df["Targeting"],
        "match_type": df["Match Type"],
        "impressions": pd.to_numeric(df["Impressions"], errors="coerce").fillna(0).astype(int),
        "clicks": pd.to_numeric(df["Clicks"], errors="coerce").fillna(0).astype(int),
        "spend": pd.to_numeric(df["Spend"], errors="coerce").fillna(0.0),
        "sales_7d": pd.to_numeric(df["7 Day Total Sales "], errors="coerce").fillna(0.0),
        "orders_7d": pd.to_numeric(df["7 Day Total Orders (#)"], errors="coerce").fillna(0).astype(int),
    }).dropna(subset=["campaign_id"])


def _build_fact_business_report(br: pd.DataFrame, snapshot_date: str = "2025-03-11") -> pd.DataFrame:
    """Business Report is a single snapshot — no date column in the file itself,
    so we set it from the filename / known reporting date."""
    return pd.DataFrame({
        "snapshot_date": pd.to_datetime(snapshot_date).date(),
        "asin": br["(Parent) ASIN"],
        "sessions_total": pd.to_numeric(br["Sessions - Total"], errors="coerce").fillna(0).astype(int),
        "page_views_total": pd.to_numeric(br["Page Views - Total"], errors="coerce").fillna(0).astype(int),
        "buy_box_pct": br["Featured Offer (Buy Box) Percentage"]
            .astype(str).str.rstrip("%").replace("nan", None)
            .pipe(pd.to_numeric, errors="coerce"),
        "units_ordered": pd.to_numeric(br["Units Ordered"], errors="coerce").fillna(0).astype(int),
        "unit_session_pct": br["Unit Session Percentage"]
            .astype(str).str.rstrip("%").replace("nan", None)
            .pipe(pd.to_numeric, errors="coerce"),
        "ordered_product_sales": br["Ordered Product Sales"]
            .astype(str).str.replace(r"[$,]", "", regex=True).replace("nan", None)
            .pipe(pd.to_numeric, errors="coerce").fillna(0.0),
        "total_order_items": pd.to_numeric(br["Total Order Items"], errors="coerce").fillna(0).astype(int),
    }).dropna(subset=["asin"])


def main() -> None:
    print("Loading anonymized CSVs...")
    bulk = _read_processed("bulk_sp_campaigns.csv")
    st = _read_processed("search_term_report.csv")
    ap = _read_processed("advertised_product_report.csv")
    br = _read_processed("business_report.csv")

    print("Building dimensions...")
    dim_date = _build_dim_date(ap["Start Date"], st["Start Date"])
    dim_campaign = _build_dim_campaign(bulk)
    dim_product = _build_dim_product(ap, br)

    print("Building facts...")
    fact_ads = _build_fact_ads_daily(ap, bulk)
    fact_st = _build_fact_search_term(st, bulk)
    fact_br = _build_fact_business_report(br)

    print(f"  dim_date: {len(dim_date)} rows")
    print(f"  dim_campaign: {len(dim_campaign)} rows")
    print(f"  dim_product: {len(dim_product)} rows")
    print(f"  fact_ads_daily: {len(fact_ads)} rows")
    print(f"  fact_search_term: {len(fact_st)} rows")
    print(f"  fact_business_report: {len(fact_br)} rows")

    print(f"\nCreating warehouse at {DB_PATH}...")
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)

    with open(SCHEMA_SQL) as f:
        conn.executescript(f.read())

    dim_date.to_sql("dim_date", conn, if_exists="append", index=False)
    dim_campaign.to_sql("dim_campaign", conn, if_exists="append", index=False)
    dim_product.to_sql("dim_product", conn, if_exists="append", index=False)
    fact_ads.to_sql("fact_ads_daily", conn, if_exists="append", index=False)
    fact_st.to_sql("fact_search_term", conn, if_exists="append", index=False)
    fact_br.to_sql("fact_business_report", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
