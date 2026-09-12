"""Drop an Iceberg table after Postgres migration + backup verification."""
from __future__ import annotations

import argparse
import json

from app.core.iceberg import get_catalog, uses_postgres
from app.core.logging import get_logger
from app.core.postgres_store import get_postgres_catalog

logger = get_logger(__name__)
NAMESPACE = ("investflow",)


def drop_iceberg_table(table_name: str, require_postgres: bool = True) -> dict:
    if require_postgres and not uses_postgres(table_name):
        raise SystemExit(
            f"Refusing to drop {table_name}: not routed to Postgres "
            f"(set POSTGRES_MIGRATED_TABLES or USE_POSTGRES_STORE first)"
        )

    pg = get_postgres_catalog()
    if not pg.table_exists(table_name):
        raise SystemExit(f"Postgres table {table_name} missing — abort drop")

    pg_rows = len(pg.load_table(table_name).to_pandas())
    catalog = get_catalog()
    ident = f"{NAMESPACE[0]}.{table_name}"
    catalog.drop_table(ident)
    logger.info(f"Dropped Iceberg table {ident}; Postgres has {pg_rows} rows")
    return {"dropped": ident, "postgres_rows": pg_rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("table")
    parser.add_argument("--force", action="store_true", help="Skip postgres routing check")
    args = parser.parse_args()
    print(json.dumps(drop_iceberg_table(args.table, require_postgres=not args.force), indent=2))
