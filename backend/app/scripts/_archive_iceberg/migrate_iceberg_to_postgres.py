"""Migrate Iceberg investflow tables into Azure Postgres."""
from __future__ import annotations

import argparse
import json
from typing import List

import pyarrow as pa

from app.core.iceberg import get_catalog, read_table, table_exists
from app.core.logging import get_logger
from app.core.postgres_store import PostgresTable, ensure_table_from_arrow, get_postgres_catalog
from app.scripts.export_iceberg_docs import KNOWN_TABLES, NAMESPACE

logger = get_logger(__name__)


def migrate_table(name: str) -> dict:
    if not table_exists(NAMESPACE, name):
        return {"table": name, "status": "missing", "rows": 0}

    # Force Iceberg read regardless of migration flags
    from app.core import iceberg as iceberg_mod
    from app.core.config import settings

    # Temporarily bypass postgres routing for source read
    catalog = iceberg_mod.get_catalog()
    iceberg_table = catalog.load_table((*NAMESPACE, name))
    arrow = iceberg_table.scan().to_arrow()
    df = arrow.to_pandas()
    if "id" in df.columns and not df.empty:
        df = df.drop_duplicates(subset=["id"], keep="last")
        arrow = pa.Table.from_pandas(df, schema=arrow.schema, preserve_index=False)

    pg = get_postgres_catalog()
    ensure_table_from_arrow(pg.engine, name, arrow.schema)
    pg._schemas[name] = arrow.schema
    table = PostgresTable(name, pg.engine, arrow.schema)
    table.overwrite(arrow)
    rows = len(df)
    logger.info(f"Migrated {name}: {rows} rows → Postgres")
    return {"table": name, "status": "ok", "rows": rows}


def main(tables: List[str] | None = None) -> None:
    targets = tables or list(KNOWN_TABLES)
    results = [migrate_table(t) for t in targets]
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", nargs="*", help="Subset of tables to migrate")
    args = parser.parse_args()
    main(args.tables)
