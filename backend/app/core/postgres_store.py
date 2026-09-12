"""
Postgres-backed table store with Iceberg-like overwrite/upsert/delete API.

Used to migrate off Lakekeeper while keeping existing call sites that use
load_table().overwrite / .upsert / .delete / .schema().
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from uuid import UUID

import pandas as pd
import pyarrow as pa
from pyiceberg.expressions import EqualTo
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from app.core.database import get_engine
from app.core.logging import get_logger

logger = get_logger(__name__)

APP_SCHEMA = "app"
metadata = MetaData(schema=APP_SCHEMA)


def _sanitize_ident(name: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(f"Invalid identifier: {name}")
    return name


def _pa_to_sa(field: pa.Field):
    t = field.type
    nullable = field.nullable
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        col_type = Text()
    elif pa.types.is_boolean(t):
        col_type = Boolean()
    elif pa.types.is_int32(t) or pa.types.is_int64(t) or pa.types.is_integer(t):
        col_type = Integer()
    elif pa.types.is_floating(t):
        col_type = Float()
    elif pa.types.is_decimal(t):
        col_type = Numeric(t.precision, t.scale)
    elif pa.types.is_timestamp(t):
        col_type = DateTime()
    elif pa.types.is_date(t):
        col_type = Date()
    elif pa.types.is_list(t) or pa.types.is_struct(t) or pa.types.is_map(t):
        col_type = JSONB()
    else:
        col_type = Text()
    return Column(field.name, col_type, nullable=nullable, primary_key=(field.name == "id"))


def _arrow_schema_from_df(df: pd.DataFrame) -> pa.Schema:
    return pa.Schema.from_pandas(df, preserve_index=False)


def ensure_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{APP_SCHEMA}"'))


def ensure_table_from_arrow(engine: Engine, table_name: str, schema: pa.Schema) -> Table:
    table_name = _sanitize_ident(table_name)
    ensure_schema(engine)
    insp = inspect(engine)
    if insp.has_table(table_name, schema=APP_SCHEMA):
        return Table(table_name, metadata, autoload_with=engine, schema=APP_SCHEMA)

    cols = [_pa_to_sa(field) for field in schema]
    if not cols:
        cols = [Column("id", Text(), primary_key=True)]
    table = Table(table_name, metadata, *cols, schema=APP_SCHEMA, extend_existing=True)
    metadata.create_all(engine, tables=[table])
    logger.info(f"Created Postgres table {APP_SCHEMA}.{table_name}")
    return table


def _serialize_cell(v: Any) -> Any:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if isinstance(v, (datetime, date, Decimal, bool, int, float, str)):
        return v
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    # numpy arrays / scalars (e.g. Iceberg nested list columns)
    try:
        import numpy as np

        if isinstance(v, np.ndarray):
            return json.dumps(v.tolist())
        if isinstance(v, np.generic):
            return v.item()
    except Exception:
        pass
    # numpy types
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return v if isinstance(v, (str, int, float, bool)) else str(v)


def dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    records = []
    for _, row in df.iterrows():
        records.append({c: _serialize_cell(row[c]) for c in df.columns})
    return records


class PostgresTable:
    """Minimal Iceberg Table shim backed by Postgres."""

    def __init__(self, name: str, engine: Engine, arrow_schema: Optional[pa.Schema] = None):
        self.name = _sanitize_ident(name)
        self.engine = engine
        self._arrow_schema = arrow_schema
        if arrow_schema is not None:
            ensure_table_from_arrow(engine, self.name, arrow_schema)

    def schema(self):
        class _Schema:
            def __init__(self, arrow_schema: pa.Schema):
                self._arrow = arrow_schema

            def as_arrow(self) -> pa.Schema:
                return self._arrow

            @property
            def fields(self):
                return list(self._arrow)

        if self._arrow_schema is None:
            # Reflect from a sample read
            df = self.to_pandas()
            self._arrow_schema = _arrow_schema_from_df(df) if not df.empty else pa.schema([pa.field("id", pa.string())])
        return _Schema(self._arrow_schema)

    def to_pandas(self) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql_table(self.name, conn, schema=APP_SCHEMA)

    def scan(self):
        class _Scan:
            def __init__(self, outer: "PostgresTable"):
                self._outer = outer

            def to_pandas(self) -> pd.DataFrame:
                return self._outer.to_pandas()

            def to_arrow(self) -> pa.Table:
                df = self._outer.to_pandas()
                if self._outer._arrow_schema is not None and not df.empty:
                    try:
                        return pa.Table.from_pandas(
                            df, schema=self._outer._arrow_schema, preserve_index=False
                        )
                    except Exception:
                        pass
                return pa.Table.from_pandas(df, preserve_index=False)

        return _Scan(self)

    def overwrite(self, arrow_table: pa.Table) -> None:
        df = arrow_table.to_pandas()
        ensure_table_from_arrow(self.engine, self.name, arrow_table.schema)
        self._arrow_schema = arrow_table.schema
        # Serialize nested/object cells (numpy arrays, lists) for Postgres drivers
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].map(_serialize_cell)
        with self.engine.begin() as conn:
            conn.execute(text(f'TRUNCATE TABLE "{APP_SCHEMA}"."{self.name}"'))
            if not df.empty:
                df.to_sql(
                    self.name,
                    conn,
                    schema=APP_SCHEMA,
                    if_exists="append",
                    index=False,
                    method="multi",
                )

    def upsert(self, arrow_table: pa.Table, join_cols: Optional[Sequence[str]] = None) -> None:
        join_cols = list(join_cols or ["id"])
        incoming = arrow_table.to_pandas()
        ensure_table_from_arrow(self.engine, self.name, arrow_table.schema)
        self._arrow_schema = arrow_table.schema
        existing = self.to_pandas()
        if existing.empty:
            self.overwrite(arrow_table)
            return
        # Drop matching keys then append
        key = join_cols[0]
        if key in existing.columns and key in incoming.columns:
            existing = existing[~existing[key].astype(str).isin(incoming[key].astype(str))]
        merged = pd.concat([existing, incoming], ignore_index=True)
        self.overwrite(pa.Table.from_pandas(merged, preserve_index=False))

    def delete(self, expr: Any) -> None:
        if isinstance(expr, EqualTo):
            col = expr.term.name if hasattr(expr.term, "name") else str(expr.term)
            val = expr.literal.value if hasattr(expr.literal, "value") else expr.literal
            col = _sanitize_ident(str(col))
            with self.engine.begin() as conn:
                conn.execute(
                    text(f'DELETE FROM "{APP_SCHEMA}"."{self.name}" WHERE "{col}" = :val'),
                    {"val": str(val)},
                )
            return
        raise NotImplementedError(f"Unsupported delete expression: {expr!r}")

    def append(self, arrow_table: pa.Table) -> None:
        df = arrow_table.to_pandas()
        ensure_table_from_arrow(self.engine, self.name, arrow_table.schema)
        if df.empty:
            return
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].map(_serialize_cell)
        with self.engine.begin() as conn:
            df.to_sql(
                self.name,
                conn,
                schema=APP_SCHEMA,
                if_exists="append",
                index=False,
                method="multi",
            )


class PostgresCatalog:
    def __init__(self, engine: Optional[Engine] = None):
        self.engine = engine or get_engine()
        self._schemas: Dict[str, pa.Schema] = {}

    def load_table(self, identifier: Union[str, Tuple[str, ...]]) -> PostgresTable:
        if isinstance(identifier, tuple):
            name = identifier[-1]
        else:
            name = identifier.split(".")[-1]
        name = _sanitize_ident(name)
        schema = self._schemas.get(name)
        return PostgresTable(name, self.engine, schema)

    def create_table(self, identifier: str, schema: pa.Schema, **kwargs) -> PostgresTable:
        name = identifier.split(".")[-1]
        name = _sanitize_ident(name)
        self._schemas[name] = schema
        ensure_table_from_arrow(self.engine, name, schema)
        return PostgresTable(name, self.engine, schema)

    def table_exists(self, name: str) -> bool:
        name = _sanitize_ident(name)
        ensure_schema(self.engine)
        return inspect(self.engine).has_table(name, schema=APP_SCHEMA)


_pg_catalog: Optional[PostgresCatalog] = None


def get_postgres_catalog() -> PostgresCatalog:
    global _pg_catalog
    if _pg_catalog is None:
        _pg_catalog = PostgresCatalog()
    return _pg_catalog
