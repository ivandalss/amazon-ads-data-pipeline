-- =============================================================================
-- Amazon Ads Analytics — Warehouse Schema
-- =============================================================================
-- Star schema designed for analytical queries across Amazon Ads + Business
-- Report data. Two fact tables (granularity differs) and shared dimensions.
--
-- Target engine: SQLite (development) / PostgreSQL or any analytical engine
-- (production). Schema is dialect-agnostic on purpose.
-- =============================================================================

DROP TABLE IF EXISTS fact_ads_daily;
DROP TABLE IF EXISTS fact_search_term;
DROP TABLE IF EXISTS fact_business_report;
DROP TABLE IF EXISTS dim_campaign;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_date;

-- =============================================================================
-- DIMENSIONS
-- =============================================================================

CREATE TABLE dim_date (
    date_id        DATE PRIMARY KEY,
    year           INTEGER NOT NULL,
    month          INTEGER NOT NULL,
    week           INTEGER NOT NULL,    -- ISO week
    day_of_week    INTEGER NOT NULL,    -- 1=Mon, 7=Sun
    is_weekend     INTEGER NOT NULL     -- 0/1
);

CREATE TABLE dim_campaign (
    campaign_id      TEXT PRIMARY KEY,
    campaign_name    TEXT NOT NULL,
    portfolio_id     TEXT,
    portfolio_name   TEXT,
    targeting_type   TEXT,        -- 'Auto' / 'Manual'
    bidding_strategy TEXT,
    state            TEXT,        -- 'enabled' / 'paused' / 'archived'
    daily_budget     REAL
);

CREATE TABLE dim_product (
    asin             TEXT PRIMARY KEY,
    sku              TEXT,
    title            TEXT
);

-- =============================================================================
-- FACT TABLES
-- =============================================================================

-- Daily ad-level performance per advertised product
-- (sourced from Advertised Product Report)
CREATE TABLE fact_ads_daily (
    date_id             DATE NOT NULL,
    campaign_id         TEXT NOT NULL,
    asin                TEXT,
    sku                 TEXT,
    impressions         INTEGER,
    clicks              INTEGER,
    spend               REAL,
    sales_7d            REAL,
    orders_7d           INTEGER,
    units_7d            INTEGER,
    advertised_sku_sales_7d REAL,
    other_sku_sales_7d  REAL,
    PRIMARY KEY (date_id, campaign_id, asin),
    FOREIGN KEY (date_id)     REFERENCES dim_date(date_id),
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id),
    FOREIGN KEY (asin)        REFERENCES dim_product(asin)
);

-- Daily search-term-level performance (granularity: customer query)
-- (sourced from Search Term Report)
CREATE TABLE fact_search_term (
    date_id             DATE NOT NULL,
    campaign_id         TEXT NOT NULL,
    customer_search_term TEXT NOT NULL,
    targeting           TEXT,
    match_type          TEXT,
    impressions         INTEGER,
    clicks              INTEGER,
    spend               REAL,
    sales_7d            REAL,
    orders_7d           INTEGER,
    FOREIGN KEY (date_id)     REFERENCES dim_date(date_id),
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
);

-- Business Report: total (ads + organic) at ASIN level
-- (sourced from Business Report — point-in-time snapshot)
CREATE TABLE fact_business_report (
    snapshot_date           DATE NOT NULL,
    asin                    TEXT NOT NULL,
    sessions_total          INTEGER,
    page_views_total        INTEGER,
    buy_box_pct             REAL,
    units_ordered           INTEGER,
    unit_session_pct        REAL,
    ordered_product_sales   REAL,
    total_order_items       INTEGER,
    PRIMARY KEY (snapshot_date, asin),
    FOREIGN KEY (asin) REFERENCES dim_product(asin)
);

-- =============================================================================
-- INDEXES (additional to PKs) for common query patterns
-- =============================================================================
CREATE INDEX idx_ads_campaign_date ON fact_ads_daily(campaign_id, date_id);
CREATE INDEX idx_st_campaign_date  ON fact_search_term(campaign_id, date_id);
CREATE INDEX idx_st_search_term    ON fact_search_term(customer_search_term);
CREATE INDEX idx_br_asin           ON fact_business_report(asin);
