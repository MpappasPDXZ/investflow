"""Postgres-only table access helpers (legacy module name: iceberg).

Lakekeeper/Iceberg has been removed. All load/read/write helpers route through
`app.core.postgres_store`. Public function names are kept so existing call sites
continue to work.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Tuple

import pandas as pd
import pyarrow as pa
from pyiceberg.expressions import And, BooleanExpression, EqualTo

from app.core.config import settings
from app.core.logging import get_logger
from app.core.postgres_store import get_postgres_catalog

logger = get_logger(__name__)


def _migrated_tables() -> set[str]:
    raw = (settings.POSTGRES_MIGRATED_TABLES or "").strip()
    if not raw:
        return set()
    return {t.strip() for t in raw.split(",") if t.strip()}


def uses_postgres(table_name: str) -> bool:
    """Always True — Postgres is the only tabular store."""
    return True


def get_catalog():
    """Removed: Lakekeeper is gone. Raises if called."""
    raise RuntimeError(
        "Lakekeeper/Iceberg catalog removed. Use load_table/read_table/append_data "
        "(Postgres-only). Set USE_POSTGRES_STORE=true."
    )


def get_store_catalog(table_name: Optional[str] = None):
    return get_postgres_catalog()


def load_table(namespace: Tuple[str, ...], table_name: str):
    """Load a Postgres-backed table handle (Iceberg-like API)."""
    catalog = get_postgres_catalog()
    return catalog.load_table(table_name)


def read_table(namespace: Tuple[str, ...], table_name: str, limit: Optional[int] = None) -> pd.DataFrame:
    try:
        table = load_table(namespace, table_name)
        df = table.to_pandas()
        if limit:
            df = df.head(limit)
        return df
    except Exception as e:
        logger.error(f"Failed to read table {'.'.join((*namespace, table_name))}: {e}", exc_info=True)
        raise


def _apply_equal_to(df: pd.DataFrame, expr: EqualTo) -> pd.DataFrame:
    col = getattr(getattr(expr, "term", None), "name", None) or str(expr.term)
    lit = expr.literal
    val = getattr(lit, "value", lit)
    if col not in df.columns:
        return df.iloc[0:0]
    return df[df[col].astype(str) == str(val)]


def _apply_filter(df: pd.DataFrame, row_filter: BooleanExpression) -> pd.DataFrame:
    if isinstance(row_filter, EqualTo):
        return _apply_equal_to(df, row_filter)
    if isinstance(row_filter, And):
        left = getattr(row_filter, "left", None) or getattr(row_filter, "_left", None)
        right = getattr(row_filter, "right", None) or getattr(row_filter, "_right", None)
        # pyiceberg And may expose .left/.right or iterable of children
        parts = []
        if left is not None and right is not None:
            parts = [left, right]
        else:
            try:
                parts = list(row_filter)
            except TypeError:
                parts = getattr(row_filter, "args", None) or []
        for part in parts:
            df = _apply_filter(df, part)
        return df
    logger.warning(f"Unsupported filter type {type(row_filter)}; returning unfiltered frame")
    return df


def read_table_filtered(
    namespace: Tuple[str, ...],
    table_name: str,
    row_filter: BooleanExpression,
    selected_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    try:
        df = read_table(namespace, table_name)
        df = _apply_filter(df, row_filter)
        if selected_columns:
            df = df[[c for c in selected_columns if c in df.columns]]
        return df
    except Exception as e:
        logger.error(
            f"Failed to read filtered table {'.'.join((*namespace, table_name))}: {e}",
            exc_info=True,
        )
        raise


def table_exists(namespace: Tuple[str, ...], table_name: str) -> bool:
    return get_postgres_catalog().table_exists(table_name)


def append_data(namespace: Tuple[str, ...], table_name: str, data: pd.DataFrame):
    try:
        table = load_table(namespace, table_name)
        df = data.copy()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype("datetime64[us]")
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        table.append(arrow_table)
    except Exception as e:
        logger.error(
            f"Failed to append data to {'.'.join((*namespace, table_name))}: {e}",
            exc_info=True,
        )
        raise


def evolve_schema_if_needed(namespace: Tuple[str, ...], table_name: str, required_columns: list[str]):
    """No-op on Postgres (schema managed via ensure_table_from_arrow / SQL)."""
    logger.debug(f"evolve_schema_if_needed skipped for Postgres table {table_name}")


def upsert_data(
    namespace: Tuple[str, ...],
    table_name: str,
    data: pd.DataFrame,
    join_cols: list[str] = None,
):
    if join_cols is None:
        join_cols = ["id"]
    try:
        table = load_table(namespace, table_name)
        df = data.copy()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype("datetime64[us]")
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        table.upsert(arrow_table, join_cols=join_cols)
    except Exception as e:
        logger.error(
            f"Failed to upsert data to {'.'.join((*namespace, table_name))}: {e}",
            exc_info=True,
        )
        raise


def upsert_data_with_schema_cast(
    namespace: Tuple[str, ...],
    table_name: str,
    data: pd.DataFrame,
    join_cols: list[str] = None,
):
    """Postgres path: same as upsert_data (no Iceberg schema cast)."""
    return upsert_data(namespace, table_name, data, join_cols=join_cols)


def update_walkthrough_data(walkthrough_id: str, data: pd.DataFrame):
    from pyiceberg.expressions import EqualTo as _Eq

    NAMESPACE = ("investflow",)
    WALKTHROUGHS_TABLE = "walkthroughs"
    try:
        table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        df = data.copy()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype("datetime64[us]")
        table.delete(_Eq("id", str(walkthrough_id)))
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        table.append(arrow_table)
    except Exception as e:
        logger.error(f"Failed to update walkthrough {walkthrough_id}: {e}", exc_info=True)
        raise


def create_walkthrough_data(record: dict):
    NAMESPACE = ("investflow",)
    WALKTHROUGHS_TABLE = "walkthroughs"
    try:
        table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        df = pd.DataFrame([record])
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype("datetime64[us]")
        # Normalize date fields
        for col in df.columns:
            val = df[col].iloc[0] if len(df) else None
            if isinstance(val, (datetime, pd.Timestamp)):
                # leave timestamps; date-only columns handled by store
                pass
            elif isinstance(val, date) and not isinstance(val, datetime):
                pass
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        table.upsert(arrow_table, join_cols=["id"])
    except Exception as e:
        logger.error(f"Failed to create walkthrough: {e}", exc_info=True)
        raise
