"""Export every Postgres app.* table to ADLS as parquet + manifest."""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from azure.storage.blob import BlobServiceClient, ContentSettings
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_engine
from app.core.logging import get_logger
from app.core.postgres_store import APP_SCHEMA

logger = get_logger(__name__)

# Expected migrated tables — empty is OK only if listed here
EMPTY_OK = {"financial_performance"}


def _blob_service() -> BlobServiceClient:
    if settings.AZURE_STORAGE_CONNECTION_STRING:
        return BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
    if settings.AZURE_STORAGE_ACCOUNT_NAME and settings.AZURE_STORAGE_ACCOUNT_KEY:
        conn = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={settings.AZURE_STORAGE_ACCOUNT_NAME};"
            f"AccountKey={settings.AZURE_STORAGE_ACCOUNT_KEY};"
            f"EndpointSuffix=core.windows.net"
        )
        return BlobServiceClient.from_connection_string(conn)
    raise ValueError("Azure storage not configured")


def _upload(blob_service: BlobServiceClient, blob_path: str, data: bytes, content_type: str) -> str:
    container = settings.AZURE_STORAGE_CONTAINER_NAME or "documents"
    client = blob_service.get_blob_client(container=container, blob=blob_path)
    client.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )
    return f"{container}/{blob_path}"


def _list_app_tables() -> List[str]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            ),
            {"schema": APP_SCHEMA},
        ).fetchall()
    return [r[0] for r in rows]


def export_all() -> Dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    adls_prefix = f"backups/postgres/{ts}"
    blob_service = _blob_service()
    engine = get_engine()
    tables = _list_app_tables()
    if not tables:
        raise SystemExit(f"No tables found in schema {APP_SCHEMA}")

    manifest_tables: List[Dict[str, Any]] = []
    errors: List[str] = []

    for name in tables:
        with engine.connect() as conn:
            df = pd.read_sql_table(name, conn, schema=APP_SCHEMA)
        row_count = len(df)
        cols = list(df.columns)
        buf = io.BytesIO()
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, buf)
        data = buf.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        blob_path = f"{adls_prefix}/{name}.parquet"
        uri = _upload(blob_service, blob_path, data, "application/octet-stream")
        entry = {
            "table": name,
            "row_count": row_count,
            "columns": cols,
            "sha256": digest,
            "bytes": len(data),
            "blob": uri,
        }
        manifest_tables.append(entry)
        logger.info(f"Exported {name}: {row_count} rows → {uri}")
        if row_count == 0 and name not in EMPTY_OK:
            # Warn but don't fail — some tables may legitimately be empty
            logger.warning(f"Table {name} has 0 rows")

    expected = {
        t.strip()
        for t in (settings.POSTGRES_MIGRATED_TABLES or "").split(",")
        if t.strip()
    }
    present = {e["table"] for e in manifest_tables}
    missing = sorted(expected - present)
    if missing:
        errors.append(f"Migrated tables missing from app schema: {missing}")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema": APP_SCHEMA,
        "prefix": adls_prefix,
        "tables": manifest_tables,
        "missing_expected": missing,
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    manifest_uri = _upload(
        blob_service,
        f"{adls_prefix}/manifest.json",
        manifest_bytes,
        "application/json",
    )
    manifest["manifest_blob"] = manifest_uri

    if errors:
        raise SystemExit("; ".join(errors))

    print(json.dumps({"status": "ok", "manifest": manifest}, indent=2, default=str))
    return manifest


if __name__ == "__main__":
    export_all()
