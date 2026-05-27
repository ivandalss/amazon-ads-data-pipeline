"""
Anonymization layer.

Strips identifiable brand/client data from raw Amazon Ads reports so they can
be safely committed to a public repo. Uses deterministic hashing so the same
input always produces the same anonymized output (joins still work).

Run once on the raw Excel files; outputs anonymized CSVs to data/processed/.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

# ---- Identifier mapping ----
BRAND_REPLACEMENTS = {
    # Add real brand names found in raw data here. Matched case-insensitively.
    # Values are the anonymized replacements that will appear in outputs.
    # IMPORTANT: longer strings first so they replace before shorter substrings.
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

# Columns that might contain brand mentions in free-text
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
}


def sanitize_text(value: object) -> object:
    """Replace any known brand mentions in a string. Returns input unchanged
    if not a string or no matches."""
    if not isinstance(value, str):
        return value
    out = value
    for raw, replacement in BRAND_REPLACEMENTS.items():
        # Case-insensitive replace, preserving the rest of the string
        out = re.sub(re.escape(raw), replacement, out, flags=re.IGNORECASE)
    return out


def hash_id(value: object, prefix: str = "ID") -> str | object:
    """Deterministically hash an ID so joins still work but IDs are not traceable."""
    if pd.isna(value):
        return value
    digest = hashlib.sha1(str(value).encode()).hexdigest()[:10]
    return f"{prefix}_{digest}"


def sanitize_dataframe(df: pd.DataFrame, id_columns: Iterable[str] = ()) -> pd.DataFrame:
    """Sanitize text columns and hash any identifier columns provided."""
    df = df.copy()
    for col in df.columns:
        if col in TEXT_COLUMNS_TO_SANITIZE:
            df[col] = df[col].apply(sanitize_text)
    for col in id_columns:
        if col in df.columns:
            prefix = col.replace(" ", "_").replace("ID", "ID")
            df[col] = df[col].apply(lambda v: hash_id(v, prefix=prefix))
    return df


# ---- Per-report processors ----

def process_bulk_file(input_path: Path, output_dir: Path) -> None:
    """Bulk file has multiple sheets. We keep Sponsored Products Campaigns
    (the main one) and discard the rest for the public project."""
    df = pd.read_excel(input_path, sheet_name="Sponsored Products Campaigns")
    df = sanitize_dataframe(
        df,
        id_columns=["Campaign ID", "Ad Group ID", "Portfolio ID", "Ad ID",
                    "Keyword ID", "Product Targeting ID"],
    )
    out = output_dir / "bulk_sp_campaigns.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


def process_search_term(input_path: Path, output_dir: Path) -> None:
    df = pd.read_excel(input_path)
    df = sanitize_dataframe(df)
    out = output_dir / "search_term_report.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


def process_advertised_product(input_path: Path, output_dir: Path) -> None:
    df = pd.read_excel(input_path)
    df = sanitize_dataframe(df)
    out = output_dir / "advertised_product_report.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


def process_business_report(input_path: Path, output_dir: Path) -> None:
    df = pd.read_excel(input_path)
    df = sanitize_dataframe(df)
    out = output_dir / "business_report.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.name} ({len(df):,} rows)")


def main() -> None:
    here = Path(__file__).resolve().parent.parent
    raw_dir = here / "data" / "raw"
    processed_dir = here / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    print("Anonymizing raw reports...")
    process_bulk_file(raw_dir / "1__Bulk_File.xlsx", processed_dir)
    process_search_term(raw_dir / "4__STR_-_Sponsored_Products_Search_term_report__1_.xlsx", processed_dir)
    process_advertised_product(raw_dir / "3__Product_-_Sponsored_Products_Advertised_product_report.xlsx", processed_dir)
    process_business_report(raw_dir / "7__Copy_of_BusinessReport-3-11-25.xlsx", processed_dir)
    print("Done. Anonymized CSVs in data/processed/.")


if __name__ == "__main__":
    main()
