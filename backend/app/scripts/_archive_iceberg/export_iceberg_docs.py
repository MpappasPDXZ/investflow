"""Export every investflow Iceberg table to local docs + ADLS (parquet + markdown)."""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.core.config import settings
from app.core.iceberg import get_catalog, read_table, table_exists
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = ("investflow",)
KNOWN_TABLES = [
    "users",
    "user_shares",
    "properties",
    "units",
    "tenants",
    "tenant_landlord_references",
    "leases",
    "rents",
    "expenses",
    "vault",
    "scheduled_expenses",
    "scheduled_revenue",
    "comps",
    "walkthroughs",
    "walkthrough_areas",
    "financial_performance",
]

DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
MARKDOWN_ROWS_PER_FILE = 500


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


def _df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._\n"
    cols = list(df.columns)

    def cell(v: Any) -> str:
        if pd.isna(v):
            return ""
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(cell(row[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def _schema_fields(table_name: str) -> List[Dict[str, Any]]:
    catalog = get_catalog()
    table = catalog.load_table(f"{NAMESPACE[0]}.{table_name}")
    fields = []
    for field in table.schema().fields:
        fields.append(
            {
                "name": field.name,
                "type": str(field.field_type),
                "required": field.required,
            }
        )
    return fields


def _infer_relationships(all_schemas: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    table_names = set(all_schemas.keys())
    rels = []
    for table, fields in all_schemas.items():
        for f in fields:
            name = f["name"]
            if name.endswith("_id") and name != "id":
                target = name[:-3]
                # pluralize naive
                candidates = [target, f"{target}s", target.rstrip("s") + "ies" if target.endswith("y") else ""]
                for c in candidates:
                    if c in table_names:
                        rels.append(f"{table}.{name} → {c}.id")
                        break
                else:
                    if target in ("property", "user", "unit", "tenant", "lease", "document"):
                        plural = {
                            "property": "properties",
                            "user": "users",
                            "unit": "units",
                            "tenant": "tenants",
                            "lease": "leases",
                            "document": "vault",
                        }.get(target)
                        if plural and plural in table_names:
                            rels.append(f"{table}.{name} → {plural}.id")
    return sorted(set(rels))


def _write_data_model(path: Path, schemas: Dict[str, List[Dict[str, Any]]], row_counts: Dict[str, int]) -> None:
    lines = [
        "# InvestFlow data model",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Source: Iceberg namespace `investflow` via Lakekeeper (pre-Postgres migration snapshot).",
        "",
        "## Tables",
        "",
    ]
    for table in sorted(schemas.keys()):
        lines.append(f"### `{table}` ({row_counts.get(table, 0)} rows)")
        lines.append("")
        lines.append("| Column | Type | Required |")
        lines.append("|--------|------|----------|")
        for f in schemas[table]:
            lines.append(f"| `{f['name']}` | `{f['type']}` | {f['required']} |")
        lines.append("")

    rels = _infer_relationships(schemas)
    lines.append("## Relationships (inferred from `*_id` columns)")
    lines.append("")
    if rels:
        for r in rels:
            lines.append(f"- `{r}`")
    else:
        lines.append("_None inferred._")
    lines.append("")
    lines.append("## ER diagram")
    lines.append("")
    lines.append("```mermaid")
    lines.append("erDiagram")
    for table, fields in sorted(schemas.items()):
        lines.append(f"  {table} {{")
        for f in fields[:12]:
            t = f["type"].replace(" ", "_")[:24]
            lines.append(f"    {t} {f['name']}")
        if len(fields) > 12:
            lines.append("    string _more_columns")
        lines.append("  }")
    for r in rels:
        # table.col → other.id
        left, right = r.split(" → ")
        lt = left.split(".")[0]
        rt = right.split(".")[0]
        lines.append(f"  {lt} }}o--|| {rt} : {left.split('.')[1]}")
    lines.append("```")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def export_all() -> Dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    local_dir = DOCS_ROOT / "exports" / ts
    local_dir.mkdir(parents=True, exist_ok=True)
    adls_prefix = f"backups/docs/{ts}"
    blob_service = _blob_service()

    catalog = get_catalog()
    # Discover tables: prefer known list intersected with what exists
    tables: List[str] = []
    for name in KNOWN_TABLES:
        if table_exists(NAMESPACE, name):
            tables.append(name)
        else:
            logger.warning(f"Table missing, skip: {name}")

    schemas: Dict[str, List[Dict[str, Any]]] = {}
    row_counts: Dict[str, int] = {}
    adls_paths: Dict[str, Dict[str, str]] = {}

    for name in tables:
        logger.info(f"Exporting {name}…")
        df = read_table(NAMESPACE, name)
        if "id" in df.columns and not df.empty:
            df = df.drop_duplicates(subset=["id"], keep="last")
        row_counts[name] = len(df)
        schemas[name] = _schema_fields(name)

        # Parquet
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq_path = local_dir / f"{name}.parquet"
        pq.write_table(table, pq_path)
        with open(pq_path, "rb") as f:
            pq_bytes = f.read()
        adls_pq = _upload(blob_service, f"{adls_prefix}/{name}.parquet", pq_bytes, "application/octet-stream")

        # Markdown (chunked)
        md_parts: List[str] = [f"# `{name}` — {len(df)} rows\n\n"]
        if df.empty:
            md_parts.append("_No rows._\n")
            md_file = local_dir / f"{name}.md"
            md_file.write_text("".join(md_parts), encoding="utf-8")
            adls_md = _upload(
                blob_service,
                f"{adls_prefix}/{name}.md",
                md_file.read_bytes(),
                "text/markdown",
            )
        else:
            chunks = []
            for i in range(0, len(df), MARKDOWN_ROWS_PER_FILE):
                chunk = df.iloc[i : i + MARKDOWN_ROWS_PER_FILE]
                part_name = f"{name}.md" if i == 0 and len(df) <= MARKDOWN_ROWS_PER_FILE else f"{name}_part{i // MARKDOWN_ROWS_PER_FILE + 1}.md"
                body = f"# `{name}` rows {i + 1}–{i + len(chunk)}\n\n" + _df_to_markdown(chunk)
                part_path = local_dir / part_name
                part_path.write_text(body, encoding="utf-8")
                adls_part = _upload(
                    blob_service,
                    f"{adls_prefix}/{part_name}",
                    part_path.read_bytes(),
                    "text/markdown",
                )
                chunks.append(adls_part)
            adls_md = chunks[0] if len(chunks) == 1 else ",".join(chunks)

        adls_paths[name] = {"parquet": adls_pq, "markdown": adls_md}

    # data-model.md
    data_model_path = DOCS_ROOT / "data-model.md"
    _write_data_model(data_model_path, schemas, row_counts)
    _upload(blob_service, f"{adls_prefix}/data-model.md", data_model_path.read_bytes(), "text/markdown")

    # manifest
    manifest = {
        "timestamp": ts,
        "namespace": "investflow",
        "tables": row_counts,
        "adls_prefix": adls_prefix,
        "adls_paths": adls_paths,
        "local_dir": str(local_dir),
    }
    manifest_md = [
        f"# Export manifest `{ts}`",
        "",
        f"ADLS prefix: `{adls_prefix}`",
        "",
        "| Table | Rows | Parquet |",
        "|-------|-----:|---------|",
    ]
    for name in tables:
        manifest_md.append(f"| `{name}` | {row_counts[name]} | `{adls_paths[name]['parquet']}` |")
    manifest_md.append("")
    manifest_path = local_dir / "manifest.md"
    manifest_path.write_text("\n".join(manifest_md), encoding="utf-8")
    (local_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _upload(blob_service, f"{adls_prefix}/manifest.md", manifest_path.read_bytes(), "text/markdown")
    _upload(
        blob_service,
        f"{adls_prefix}/manifest.json",
        (local_dir / "manifest.json").read_bytes(),
        "application/json",
    )

    logger.info(f"Export complete: {ts} — {sum(row_counts.values())} total rows across {len(tables)} tables")
    return manifest


def main() -> None:
    manifest = export_all()
    print(json.dumps({k: manifest[k] for k in ("timestamp", "tables", "adls_prefix", "local_dir")}, indent=2))


if __name__ == "__main__":
    main()
