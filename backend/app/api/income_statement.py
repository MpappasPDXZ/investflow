"""API route for income statement PDF generation (T12 and calendar year)"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from uuid import UUID
from datetime import date
from typing import List
import io

import pandas as pd

from app.core.dependencies import get_current_user
from app.core.iceberg import table_exists, read_table
from app.core.logging import get_logger
from app.services.income_statement_service import income_statement_service

router = APIRouter(prefix="/income-statement", tags=["income-statement"])
logger = get_logger(__name__)

NAMESPACE = ("investflow",)


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

        if mode == "calendar":
            filename = f"income_statement_{year}.pdf"
        else:
            today = date.today()
            filename = f"income_statement_T12_{today.strftime('%Y%m%d')}.pdf"

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
