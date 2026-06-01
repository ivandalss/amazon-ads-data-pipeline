"""
MMM Data Preparation
====================
Pulls weekly aggregated data from the warehouse (fact_ads_daily +
fact_business_report) and prepares it for Marketing Mix Modeling.

Because the sample dataset covers only ~5 weeks, this module also contains
a synthetic data generator that produces 2 years of realistic weekly data
with the same schema. The synthetic data is clearly labelled and documented.

Outputs
-------
data/mmm/weekly_actuals.csv   — real data from warehouse (5 weeks)
data/mmm/weekly_synthetic.csv — 2 years of synthetic data for MMM modeling
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "data" / "warehouse.db"
MMM_DIR = HERE / "data" / "mmm"


# ── 1. Extract real data from warehouse ──────────────────────────────────────

ACTUALS_QUERY = """
SELECT
    d.year,
    d.week,
    -- Spend by match type used as a proxy for channel split
    SUM(CASE WHEN c.targeting_type = 'AUTO'    THEN f.spend ELSE 0 END) AS spend_auto,
    SUM(CASE WHEN c.targeting_type = 'MANUAL'  THEN f.spend ELSE 0 END) AS spend_manual,
    SUM(f.spend)       AS spend_total,
    SUM(f.impressions) AS impressions_total,
    SUM(f.clicks)      AS clicks_total,
    SUM(f.sales_7d)    AS ad_sales,
    SUM(f.orders_7d)   AS ad_orders
FROM fact_ads_daily f
JOIN dim_date     d ON f.date_id     = d.date_id
JOIN dim_campaign c ON f.campaign_id = c.campaign_id
GROUP BY d.year, d.week
ORDER BY d.year, d.week
"""

ORGANIC_QUERY = """
SELECT
    SUM(ordered_product_sales) AS total_sales,
    SUM(units_ordered)         AS total_units
FROM fact_business_report
"""


def extract_actuals() -> pd.DataFrame | None:
    """Pull real weekly data from the warehouse. Returns None if DB missing."""
    if not DB_PATH.exists():
        print(f"  [warn] warehouse.db not found at {DB_PATH}. Skipping actuals extract.")
        return None

    conn = sqlite3.connect(DB_PATH)
    ads_df = pd.read_sql_query(ACTUALS_QUERY, conn)
    organic = pd.read_sql_query(ORGANIC_QUERY, conn).iloc[0]
    conn.close()

    # Distribute single-snapshot organic sales evenly across weeks (rough proxy)
    n_weeks = max(len(ads_df), 1)
    ads_df["organic_sales_est"] = float(organic["total_sales"]) / n_weeks
    ads_df["total_sales_est"] = ads_df["ad_sales"] + ads_df["organic_sales_est"]

    print(f"  Extracted {len(ads_df)} weeks of actuals from warehouse.")
    return ads_df


# ── 2. Synthetic data generator ───────────────────────────────────────────────

def generate_synthetic(
    n_weeks: int = 104,  # 2 years
    seed: int = 42,
    start_date: str = "2023-01-02",
) -> pd.DataFrame:
    """
    Generate realistic synthetic weekly data for MMM modeling.

    The data is constructed from known components so we can validate
    the model's ability to recover true channel contributions:

        total_sales = baseline
                    + beta_sp   * adstock(spend_sp)   * saturation(spend_sp)
                    + beta_sb   * adstock(spend_sb)   * saturation(spend_sb)
                    + beta_dsp  * adstock(spend_dsp)  * saturation(spend_dsp)
                    + seasonality
                    + noise

    TRUE parameters (saved alongside data for model validation):
        beta_sp  = 3.5   (Sponsored Products — highest ROI)
        beta_sb  = 2.0   (Sponsored Brands)
        beta_dsp = 1.2   (DSP / display — lowest ROI, awareness play)
        baseline = 8000  (weekly organic floor)

    NOTE: This is synthetic data generated for portfolio demonstration.
    A real MMM requires ≥52 weeks of observed data.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start_date, periods=n_weeks, freq="W-MON")

    # ── Spend series: realistic weekly budgets with Q4 peaks ────────────────
    t = np.arange(n_weeks)

    # Seasonal spend multiplier — higher in Q4, lower in Q1
    spend_season = 1 + 0.4 * np.sin(2 * np.pi * (t - 10) / 52)

    spend_sp  = rng.normal(2500, 300, n_weeks) * spend_season
    spend_sb  = rng.normal(1200, 200, n_weeks) * spend_season
    spend_dsp = rng.normal(800,  150, n_weeks) * spend_season

    # Occasional promo bursts (Prime Day ~week 28, Black Friday ~week 47)
    for w in [28, 47, 79, 99]:
        if w < n_weeks:
            spend_sp[w]  *= rng.uniform(2.0, 2.8)
            spend_sb[w]  *= rng.uniform(1.5, 2.0)
            spend_dsp[w] *= rng.uniform(1.3, 1.8)

    spend_sp  = np.maximum(spend_sp,  0)
    spend_sb  = np.maximum(spend_sb,  0)
    spend_dsp = np.maximum(spend_dsp, 0)

    # ── Adstock transform (geometric decay) ────────────────────────────────
    def adstock(x: np.ndarray, decay: float) -> np.ndarray:
        """Geometric adstock: each week carries forward a fraction of prior spend."""
        out = np.zeros_like(x)
        out[0] = x[0]
        for i in range(1, len(x)):
            out[i] = x[i] + decay * out[i - 1]
        return out

    asp  = adstock(spend_sp,  decay=0.5)   # SP: moderate carryover
    asb  = adstock(spend_sb,  decay=0.3)   # SB: lower carryover (brand awareness)
    adsp = adstock(spend_dsp, decay=0.7)   # DSP: highest carryover (display/awareness)

    # ── Hill saturation transform ────────────────────────────────────────────
    def hill(x: np.ndarray, K: float, n: float = 2.0) -> np.ndarray:
        """Hill function: models diminishing returns. K = half-saturation point."""
        return x**n / (K**n + x**n)

    sat_sp  = hill(asp,  K=3000)
    sat_sb  = hill(asb,  K=1500)
    sat_dsp = hill(adsp, K=1000)

    # ── True response coefficients ──────────────────────────────────────────
    TRUE_BETA_SP  = 3.5
    TRUE_BETA_SB  = 2.0
    TRUE_BETA_DSP = 1.2
    BASELINE      = 8000

    # ── Seasonality (organic demand) ────────────────────────────────────────
    # Q4 spike + mild Q2 dip
    seasonality = (
        1500 * np.sin(2 * np.pi * (t - 8) / 52)   # annual cycle
        + 400 * np.sin(4 * np.pi * t / 52)          # bi-annual minor cycle
    )

    # ── Noise ───────────────────────────────────────────────────────────────
    noise = rng.normal(0, 400, n_weeks)

    # ── Compose total sales ──────────────────────────────────────────────────
    ad_contribution_sp  = TRUE_BETA_SP  * sat_sp  * spend_sp.mean()
    ad_contribution_sb  = TRUE_BETA_SB  * sat_sb  * spend_sb.mean()
    ad_contribution_dsp = TRUE_BETA_DSP * sat_dsp * spend_dsp.mean()

    total_sales = (
        BASELINE
        + TRUE_BETA_SP  * sat_sp  * spend_sp
        + TRUE_BETA_SB  * sat_sb  * spend_sb
        + TRUE_BETA_DSP * sat_dsp * spend_dsp
        + seasonality
        + noise
    )
    total_sales = np.maximum(total_sales, 0)

    # Derived ad metrics (realistic CTR/CVR assumptions)
    impressions = (spend_sp + spend_sb) / 0.015   # ~$0.015 CPM proxy
    clicks      = impressions * rng.uniform(0.003, 0.005, n_weeks)
    ad_sales    = total_sales * rng.uniform(0.30, 0.45, n_weeks)  # ads drive ~35% of sales
    ad_orders   = ad_sales / rng.uniform(25, 40, n_weeks)         # ~$30 AOV

    df = pd.DataFrame({
        "week_start":       dates,
        "year":             dates.year,
        "week":             dates.isocalendar().week,
        # Spend by channel
        "spend_sp":         np.round(spend_sp,  2),
        "spend_sb":         np.round(spend_sb,  2),
        "spend_dsp":        np.round(spend_dsp, 2),
        "spend_total":      np.round(spend_sp + spend_sb + spend_dsp, 2),
        # Observed metrics
        "impressions_total": np.round(impressions).astype(int),
        "clicks_total":      np.round(clicks).astype(int),
        "ad_sales":          np.round(ad_sales,   2),
        "ad_orders":         np.round(ad_orders).astype(int),
        "total_sales":       np.round(total_sales, 2),
        "organic_sales":     np.round(total_sales - ad_sales, 2),
        # Computed KPIs
        "roas":   np.round(ad_sales / (spend_sp + spend_sb + spend_dsp + 1e-9), 3),
        "tacos":  np.round((spend_sp + spend_sb + spend_dsp) / (total_sales + 1e-9), 3),
        "ctr":    np.round(clicks / (impressions + 1e-9), 4),
    })

    # Save true parameters alongside data (for model validation)
    true_params = pd.DataFrame([{
        "param": "beta_sp",  "value": TRUE_BETA_SP,
        "description": "Sponsored Products response coefficient"
    }, {
        "param": "beta_sb",  "value": TRUE_BETA_SB,
        "description": "Sponsored Brands response coefficient"
    }, {
        "param": "beta_dsp", "value": TRUE_BETA_DSP,
        "description": "DSP response coefficient"
    }, {
        "param": "baseline", "value": BASELINE,
        "description": "Weekly organic sales floor"
    }])

    print(f"  Generated {n_weeks} weeks of synthetic data.")
    print(f"  Avg weekly spend: ${df['spend_total'].mean():,.0f}")
    print(f"  Avg weekly total sales: ${df['total_sales'].mean():,.0f}")
    print(f"  Avg TACoS: {df['tacos'].mean():.1%}")

    return df, true_params


# ── 3. Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    MMM_DIR.mkdir(parents=True, exist_ok=True)

    print("Extracting actuals from warehouse...")
    actuals = extract_actuals()
    if actuals is not None:
        out = MMM_DIR / "weekly_actuals.csv"
        actuals.to_csv(out, index=False)
        print(f"  Saved → {out}")

    print("\nGenerating synthetic dataset...")
    synthetic, true_params = generate_synthetic(n_weeks=104)
    out_syn = MMM_DIR / "weekly_synthetic.csv"
    out_par = MMM_DIR / "true_parameters.csv"
    synthetic.to_csv(out_syn, index=False)
    true_params.to_csv(out_par, index=False)
    print(f"  Saved → {out_syn}")
    print(f"  Saved → {out_par} (true parameters for model validation)")
    print("\nDone. Ready for MMM modeling — open notebooks/mmm_model.ipynb")


if __name__ == "__main__":
    main()
