"""
Anonymization layer v2.

Changes from v1:
- Added ASIN pattern regex: any B0XXXXXXXX or B00XXXXXXX in free text gets hashed
- Added product name variants to BRAND_REPLACEMENTS (Enduracin, Pepzin, Niacin variants)
- ASINs now hashed in AP and BR processed CSVs
- Campaign ID and Ad Group ID hashed in STR and AP reports
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


# ── Brand name replacements ──────────────────────────────────────────────────
# IMPORTANT: longer strings must come before shorter substrings
BRAND_REPLACEMENTS = {
    "endurance products company": "Brand_A",
    "epc endurance products company": "Brand_A",
    "daily endurance": "Brand_A",
    "endur-acin": "Brand_A_Product_1",
    "endur-b": "Brand_A_Product_2",
    "enduricin": "Brand_A_Product_1",
    "enduracin": "Brand_A_Product_1",
    "endur acin": "Brand_A_Product_1",
    "endur-": "Brand_A_Product_",
    "endurance": "Brand_A",
    "pepzin gi": "Brand_A_Product_3",
    "pepzin": "Brand_A_Product_3",
    "epc": "Brand_A",
    "laco": "Brand_A",
}

# ── Text columns sanitized for brand mentions ────────────────────────────────
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

# ── URL columns ──────────────────────────────────────────────────────────────
URL_COLUMNS = {
    "Landing Page URL",
    "Image Locator",
    "Image URL",
    "Creative Asset URL",
}

# ── ASIN pattern: B0 or B00 followed by alphanumeric chars, total 10 chars ──
ASIN_PATTERN = re.compile(r'\bB0[A-Z0-9]{8}\b')


def _hash_asin_match(match: re.Match) -> str:
    """Replace a regex ASIN match with a deterministic hash."""
    digest = hashlib.sha1(match.group(0).encode()).hexdigest()[:8].upper()
    return f"ASIN_{digest}"


def sanitize_text(value: object) -> object:
    """Replace brand mentions AND embedded ASINs in a string."""
    if not isinstance(value, str):
        return value
    out = value
    # 1. Replace brand names
    for raw, replacement in BRAND_REPLACEMENTS.items():
        out = re.sub(re.escape(raw), replacement, out, flags=re.IGNORECASE)
    # 2. Replace any remaining ASIN patterns (e.g. B0BFWDTPKP in campaign names)
    out = ASIN_PATTERN.sub(_hash_asin_match, out)
    return out


def hash_id(value: object, prefix: str = "ID") -> str | object:
    """Deterministically hash an ID — joins still work across reports."""
    if pd.isna(value):
        return value
    digest = hashlib.sha1(str(value).encode()).hexdigest()[:10]
    return f"{prefix}_{digest}"


# Different Amazon reports label the same real-world entity with different
# column headers ("ASIN" in one, "Advertised ASIN" in another, "ASIN
# (Informational only)" in a third). hash_id()'s prefix used to be derived
# from each column's own name, so the same underlying ASIN/SKU hashed to a
# different-looking string per report (same digest, different prefix) —
# breaking any downstream join on that identifier across reports, even
# though the two values represented the same real product. This map forces
# a single canonical prefix for columns known to carry the same identifier
# space across reports, so sanitize_dataframe() below produces IDENTICAL
# anonymized values for the same real ASIN/SKU no matter which report or
# column name it came from.
CANONICAL_ID_PREFIXES = {
    "ASIN": "ASIN",
    "Advertised ASIN": "ASIN",
    "ASIN (Informational only)": "ASIN",
    "(Parent) ASIN": "ASIN",
    "(Child) ASIN": "ASIN",
    "SKU": "SKU",
    "Advertised SKU": "SKU",
}


def hash_url(value: object) -> str | object:
    """Replace a URL with a hashed placeholder."""
    if pd.isna(value) or not isinstance(value, str) or value.strip() == "":
        return value
    digest = hashlib.sha1(value.encode()).hexdigest()[:12]
    return f"https://hashed-url.example/{digest}"


def sanitize_dataframe(
    df: pd.DataFrame,
    id_columns: Iterable[str] = (),
) -> pd.DataFrame:
    """Apply all anonymization transforms."""
    df = df.copy()
    # 1. Text sanitization (brand names + embedded ASINs)
    for col in df.columns:
        if col in TEXT_COLUMNS_TO_SANITIZE:
            df[col] = df[col].apply(sanitize_text)
    # 2. ID hashing
    for col in id_columns:
        if col in df.columns:
            prefix = CANONICAL_ID_PREFIXES.get(col) or (
                col.replace(" ", "_").replace("(", "").replace(")", "").strip("_")
            )
            df[col] = df[col].apply(lambda v, p=prefix: hash_id(v, prefix=p))
    # 3. URL scrubbing
    for col in df.columns:
        if col in URL_COLUMNS:
            df[col] = df[col].apply(hash_url)
    return df


# ── Per-report processors ────────────────────────────────────────────────────

def process_bulk_file(input_path: Path, output_dir: Path) -> None:
    df = pd.read_excel(input_path, sheet_name="Sponsored Products Campaigns")
    df = sanitize_dataframe(
        df,
        id_columns=[
            "Campaign ID", "Ad Group ID", "Portfolio ID",
            "Ad ID", "Keyword ID", "Product Targeting ID",
            # Real header is "ASIN (Informational only)", not "ASIN" - the
            # plain "ASIN" entry never matched a column in this report, so
            # this field was silently skipped and shipped un-anonymized.
            # See CANONICAL_ID_PREFIXES above for why this also needs to
            # hash to the same value as "Advertised ASIN" elsewhere.
            "ASIN (Informational only)", "SKU",
        ],
    )
    out = output_dir / "bulk_sp_campaigns.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


def process_search_term(input_path: Path, output_dir: Path) -> None:
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

    print("Done.")
    print("\nAnonymization coverage:")
    print("  + Brand names replaced in all text columns")
    print("  + ASINs hashed in dedicated columns (AP, BR, STR)")
    print("  + ASINs embedded in Campaign Names replaced via regex")
    print("  + Campaign/Ad Group IDs hashed across all reports")
    print("  + SKUs hashed in bulk and AP reports")
    print("  + URLs scrubbed in bulk file")


if __name__ == "__main__":
    main()
