#!/usr/bin/env python3
"""
Print the Iceberg vault table (document metadata) schema and sample rows.

Shows: id, user_id, blob_name, file_name, document_type so you can compare
with the IDs in your Excel (vault.id is the document UUID; blob_name is the path in Azure).

Usage (from backend dir, with Lakekeeper running):
  uv run python -m app.scripts.inspect_vault
  uv run python -m app.scripts.inspect_vault --rows 5
"""
import argparse
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from app.core.iceberg import get_catalog
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Inspect investflow.vault schema and sample rows")
    parser.add_argument("--rows", type=int, default=20, help="Number of sample rows (default 20)")
    parser.add_argument("--user", type=str, default=None, help="Filter by user_id (optional)")
    args = parser.parse_args()

    catalog = get_catalog()
    table = catalog.load_table("investflow.vault")

    # Schema
    schema = table.schema()
    print("=== investflow.vault schema ===\n")
    for field in schema.fields:
        print(f"  {field.name}: {field.field_type}")

    # Sample rows
    print(f"\n=== Sample rows (up to {args.rows}) ===\n")
    scan = table.scan()
    arrow_table = scan.to_arrow()
    df = pd.DataFrame(arrow_table.to_pylist())

    if args.user:
        df = df[df["user_id"].astype(str) == args.user]

    df = df.head(args.rows)

    # Key columns for comparing with Excel
    cols = ["id", "user_id", "blob_name", "file_name", "document_type"]
    available = [c for c in cols if c in df.columns]
    if not available:
        available = list(df.columns)[:10]
    print(df[available].to_string())

    print("\n--- Note: Excel 'ID' may be vault.id (document UUID) or part of blob_name. Compare above with your Excel IDs.")


if __name__ == "__main__":
    main()
