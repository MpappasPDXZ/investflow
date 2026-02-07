"""
Coerce pandas / Decimal / numpy values for Pydantic response schemas.

Key problem: pandas stores missing values as float NaN, which is *truthy*.
So `if row.get("unit_id")` passes for NaN, then UUID(NaN) explodes.
clean_pandas_dict() replaces all NaN with None in one pass, making
standard Python truthiness checks (if v:) safe again.
"""
from decimal import Decimal
from typing import Any
from uuid import UUID as _UUID
from datetime import datetime, date

try:
    import pandas as pd
    HAS_PD = True
except ImportError:
    HAS_PD = False


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def _is_na(v: Any) -> bool:
    if v is None:
        return True
    if HAS_PD and pd.isna(v):
        return True
    if isinstance(v, float) and v != v:
        return True
    return False


def to_int_required(v: Any) -> int:
    """Coerce to int (e.g. from Decimal, float, numpy.int64). For required int fields."""
    if _is_na(v):
        return 0
    if isinstance(v, Decimal):
        return int(v)
    if hasattr(v, "item"):
        return int(v.item())
    return int(float(v))


def to_int_or_none(v: Any) -> int | None:
    """Coerce to int or None."""
    if _is_na(v):
        return None
    if isinstance(v, Decimal):
        return int(v)
    if hasattr(v, "item"):
        return int(v.item())
    return int(float(v))


# ---------------------------------------------------------------------------
# Dict-level helpers  (use on row.to_dict() *before* passing to Pydantic)
# ---------------------------------------------------------------------------

def clean_pandas_dict(d: dict) -> dict:
    """Replace every NaN value in *d* with None (in-place + returned).

    This is the single most important defence: after calling this, normal
    ``if v:`` / ``if v is not None:`` checks work correctly because None
    is falsy while float('nan') is truthy.
    """
    for k, v in d.items():
        if isinstance(v, float) and v != v:          # fast NaN check
            d[k] = None
        elif HAS_PD and isinstance(v, float) and pd.isna(v):
            d[k] = None
    return d


def str_or_none(v: Any) -> str | None:
    """Convert a pandas/numpy value to ``str`` or ``None``."""
    if _is_na(v):
        return None
    return str(v) if not isinstance(v, str) else v


def uuid_or_none(v: Any) -> _UUID | None:
    """Convert a string/UUID to UUID, or None if missing/NaN."""
    if _is_na(v):
        return None
    if isinstance(v, _UUID):
        return v
    s = str(v)
    if s in ("", "None"):
        return None
    try:
        return _UUID(s)
    except (ValueError, AttributeError):
        return None


def date_or_none(v: Any) -> date | None:
    """Convert a pandas/string value to a Python date, or None."""
    if _is_na(v):
        return None
    if HAS_PD:
        try:
            return pd.Timestamp(v).date()
        except Exception:
            return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def datetime_or_now(v: Any) -> datetime:
    """Convert to a native datetime; fall back to now() if missing."""
    if _is_na(v):
        return datetime.now()
    if HAS_PD:
        try:
            return pd.Timestamp(v).to_pydatetime()
        except Exception:
            return datetime.now()
    if isinstance(v, datetime):
        return v
    return datetime.now()
