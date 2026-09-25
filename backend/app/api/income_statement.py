"""API route for income statement PDF generation (T12 and calendar year)"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from uuid import UUID
from datetime import date
from typing import List
import io
import re

import pandas as pd

from app.core.dependencies import get_current_user
from app.core.iceberg import table_exists, read_table
from app.core.logging import get_logger
from app.services.income_statement_service import income_statement_service

router = APIRouter(prefix="/income-statement", tags=["income-statement"])
logger = get_logger(__name__)

NAMESPACE = ("investflow",)


def _address_slug(address: str, length: int = 5) -> str:
    """Slugify address for filenames: spaces/non-alnum -> _, first `length` chars."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", (address or "").strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return (slug[:length] if slug else "prop")


def _income_statement_filename(
    mode: str,
    year: int,
    address_line1: str = "",
    display_name: str = "",
) -> str:
    """Build download name: {YYYYMM}_{FY_year|T12}_{AddrSlug}.pdf"""
    run_stamp = date.today().strftime("%Y%m")
    report_name = f"FY_{year}" if mode == "calendar" else "T12"
    addr_slug = _address_slug(address_line1 or display_name)
    return f"{run_stamp}_{report_name}_{addr_slug}.pdf"


@router.get("/{property_id}/years")
async def get_available_years(
    property_id: UUID,
    current_user: dict = Depends(get_current_user),
) -> List[int]:
    """Return distinct calendar years that have expense or rent data for a property."""
    years = set()
    pid = str(property_id)

    if table_exists(NAMESPACE, "expenses"):
        df = read_table(NAMESPACE, "expenses")
        df = df[df["property_id"] == pid]
        if "date" in df.columns and len(df) > 0:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            years.update(df["date"].dropna().dt.year.unique())

    if table_exists(NAMESPACE, "rents"):
        df = read_table(NAMESPACE, "rents")
        df = df[df["property_id"] == pid]
        if "rent_period_year" in df.columns and len(df) > 0:
            years.update(int(y) for y in df["rent_period_year"].dropna().unique())

    return sorted(years, reverse=True)


@router.get("/{property_id}/pdf")
async def generate_income_statement_pdf(
    property_id: UUID,
    year: int = Query(default=None, description="Calendar year for 'calendar' mode (defaults to current year)"),
    mode: str = Query(default="t12", description="Report mode: 't12' for trailing 12 months, 'calendar' for Jan-Dec"),
    current_user: dict = Depends(get_current_user),
):
    """Generate and download an income statement PDF for a property."""
    try:
        if year is None:
            year = date.today().year

        pdf_bytes = income_statement_service.generate_pdf(
            property_id=str(property_id),
            fiscal_year=year,
            mode=mode,
        )

        address_line1 = ""
        display_name = ""
        if table_exists(NAMESPACE, "properties"):
            props = read_table(NAMESPACE, "properties")
            rows = props[props["id"] == str(property_id)]
            if len(rows) > 0:
                row = rows.iloc[0]
                address_line1 = str(row.get("address_line1") or "")
                display_name = str(row.get("display_name") or "")

        filename = _income_statement_filename(mode, year, address_line1, display_name)

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating income statement: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
