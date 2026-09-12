#!/usr/bin/env python3
"""
Search the vault table for a document ID (by vault.id or by blob_name containing it).

Usage (from backend dir, Lakekeeper running):
  uv run python -m app.scripts.find_vault_doc d4c8912c-70bc-4a9f-a59e-9986c217d651
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from pyiceberg.expressions import EqualTo
from app.core.iceberg import get_catalog


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python -m app.scripts.find_vault_doc <document-id-uuid>")
        sys.exit(1)
    target = sys.argv[1].strip()
    target_no_dash = target.replace("-", "")

    catalog = get_catalog()
    table = catalog.load_table("investflow.vault")

    # 1) By vault id
    scan = table.scan(row_filter=EqualTo("id", target))
    arrow = scan.to_arrow()
    rows = arrow.to_pylist()
    if rows:
        print("Found by vault.id:")
        for r in rows:
            print("  id:", r.get("id"))
            print("  user_id:", r.get("user_id"))
            print("  blob_name:", r.get("blob_name"))
            print("  file_name:", r.get("file_name"))
        return

    print("Not found by vault.id")

    # 2) Any row where blob_name contains this id
    scan_all = table.scan()
    full = scan_all.to_arrow().to_pylist()
    matches = [
        r
        for r in full
        if r.get("blob_name")
        and (
            target in str(r.get("blob_name", ""))
            or target_no_dash in str(r.get("blob_name", "")).replace("-", "")
        )
    ]
    if matches:
        print("Found by blob_name containing id:")
        for r in matches:
            print("  id:", r.get("id"))
            print("  user_id:", r.get("user_id"))
            print("  blob_name:", r.get("blob_name"))
            print("  file_name:", r.get("file_name"))
    else:
        print("Not found in blob_name in any row.")
        print("Total vault rows:", len(full))


if __name__ == "__main__":
    main()
