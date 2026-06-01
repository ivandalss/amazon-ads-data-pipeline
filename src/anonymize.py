"""
Anonymization layer.

Strips identifiable brand/client data from raw Amazon Ads reports so they can
be safely committed to a public repo. Uses deterministic hashing so the same
input always produces the same anonymized output (joins still work).

Run once on the raw Excel files; outputs anonymized CSVs to data/processed/.

Anonymization coverage
----------------------
Text sanitization  — brand names replaced in all free-text columns
ID hashing         — all IDs, ASINs, SKUs, and URLs hashed across all reports
URL scrubbing      — landing page and image URLs replaced with hashed placeholders

Known limitations
-----------------
- Product titles are sanitized for known brand keywords but the full title
  structure (e.g. "500mg Vitamin C Tablet 120 count") may still hint at
  the product category. Acceptable for public portfolio use.
- BRAND_REPLACEMENTS must be kept up to date if new brand variants appear
  in raw data. Add longer strings before shorter substrings.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


# ── Brand name replacements ──────────────────────────────────────────────────
BRAND_REPLACEMENTS = {
    "endurance products company": "Brand_A",
    "epc endurance products company": "Brand_A",
    "daily endurance": "Brand_A",
    "endur-acin": "Brand_A_Product_1",
    "endur-b": "Brand_A_Product_2",
    "enduricin": "Brand_A_Product_1",
    "endur-": "Brand_A_Product_",
    "endurance": "Brand_A",
    "epc": "Brand_A",
    "laco": "Brand_A",
}

# ── Columns sanitized for brand text mentions ────────────────────────────────
TEXT_COLUMNS_TO_SANITIZE = {
    "Campaign Name",
    "Campaign Name (Informational only)",
    "Ad Group Name",
    "Ad Group Name (Informational only)",
    "Portfolio Name (Informational only)",
    "Portfolio name",
    "Keyword Text",
    "Customer Search Term",
    "Targeting",
    "Product Targeting Expression",
    "Resolved Product Targeting Expression (Informational only)",
    "Title",
    "Product Name",
    "Description",
}

# ── URL columns: replace with hashed placeholder ─────────────────────────────
URL_COLUMNS = {
    "Landing Page URL",
    "Image Locator",
    "Image URL",
    "Creative Asset URL",
}


# ── Core transform functions ─────────────────────────────────────────────────

def sanitize_text(value: object) -> object:
    """Replace known brand mentions in a string."""
    if not isinstance(value, str):
        return value
    out = value
    for raw, replacement in BRAND_REPLACEMENTS.items():
        out = re.sub(re.escape(raw), replacement, out, flags=re.IGNORECASE)
    return out


def hash_id(value: object, prefix: str = "ID") -> str | object:
    """Deterministically hash an ID so joins still work but values are not
    traceable back to the original client data."""
    if pd.isna(value):
        return value
    digest = hashlib.sha1(str(value).encode()).hexdigest()[:10]
    return f"{prefix}_{digest}"


def hash_url(value: object) -> str | object:
    """Replace a URL with a hashed placeholder that preserves uniqueness."""
    if pd.isna(value) or not isinstance(value, str) or value.strip() == "":
        return value
    digest = hashlib.sha1(value.encode()).hexdigest()[:12]
    return f"https://hashed-url.example/{digest}"


def sanitize_dataframe(
    df: pd.DataFrame,
    id_columns: Iterable[str] = (),
) -> pd.DataFrame:
    """
    Apply all anonymization transforms to a dataframe:
    1. Brand text replacement in TEXT_COLUMNS_TO_SANITIZE
    2. Deterministic hashing of id_columns
    3. URL scrubbing of URL_COLUMNS
    """
    df = df.copy()

    # 1. Text sanitization
    for col in df.columns:
        if col in TEXT_COLUMNS_TO_SANITIZE:
            df[col] = df[col].apply(sanitize_text)

    # 2. ID hashing
    for col in id_columns:
        if col in df.columns:
            prefix = col.replace(" ", "_").replace("(", "").replace(")", "").strip("_")
            df[col] = df[col].apply(lambda v: hash_id(v, prefix=prefix))

    # 3. URL scrubbing
    for col in df.columns:
        if col in URL_COLUMNS:
            df[col] = df[col].apply(hash_url)

    return df


# ── Per-report processors ────────────────────────────────────────────────────

def process_bulk_file(input_path: Path, output_dir: Path) -> None:
    """Bulk file: hash all IDs + ASINs + SKUs + URLs."""
    df = pd.read_excel(input_path, sheet_name="Sponsored Products Campaigns")
    df = sanitize_dataframe(
        df,
        id_columns=[
            # Structural IDs
            "Campaign ID", "Ad Group ID", "Portfolio ID",
            "Ad ID", "Keyword ID", "Product Targeting ID",
            # Product identifiers
            "ASIN", "SKU",
        ],
    )
    out = output_dir / "bulk_sp_campaigns.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


def process_search_term(input_path: Path, output_dir: Path) -> None:
    """Search Term Report: hash IDs + ASINs."""
    df = pd.read_excel(input_path)
    df = sanitize_dataframe(
        df,
        id_columns=[
            "Campaign ID", "Ad Group ID",
            "Advertised ASIN", "ASIN",
        ],
    )
    out = output_dir / "search_term_report.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


def process_advertised_product(input_path: Path, output_dir: Path) -> None:
    """Advertised Product Report: hash IDs + ASINs + SKUs."""
    df = pd.read_excel(input_path)
    df = sanitize_dataframe(
        df,
        id_columns=[
            "Campaign ID", "Ad Group ID",
            "Advertised ASIN", "Advertised SKU",
            "ASIN", "SKU",
        ],
    )
    out = output_dir / "advertised_product_report.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


def process_business_report(input_path: Path, output_dir: Path) -> None:
    """Business Report: hash ASINs (parent + child)."""
    df = pd.read_excel(input_path)
    df = sanitize_dataframe(
        df,
        id_columns=[
            "(Parent) ASIN", "(Child) ASIN",
            "ASIN",
        ],
    )
    out = output_dir / "business_report.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    here = Path(__file__).resolve().parent.parent
    raw_dir = here / "data" / "raw"
    processed_dir = here / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    print("Anonymizing raw reports...")
    process_bulk_file(
        raw_dir / "1__Bulk_File.xlsx", processed_dir)
    process_search_term(
        raw_dir / "4__STR_-_Sponsored_Products_Search_term_report__1_.xlsx", processed_dir)
    process_advertised_product(
        raw_dir / "3__Product_-_Sponsored_Products_Advertised_product_report.xlsx", processed_dir)
    process_business_report(
        raw_dir / "7__Copy_of_BusinessReport-3-11-25.xlsx", processed_dir)

    print("Done. Anonymized CSVs written to data/processed/.")
    print("\nAnonymization coverage:")
    print("  ✓ Brand names replaced in all text/name columns")
    print("  ✓ Campaign/Ad Group/Portfolio/Keyword IDs hashed")
    print("  ✓ ASINs hashed across all four reports (joins preserved)")
    print("  ✓ SKUs hashed across bulk and advertised product reports")
    print("  ✓ URLs scrubbed in bulk file")


if __name__ == "__main__":
    main()
