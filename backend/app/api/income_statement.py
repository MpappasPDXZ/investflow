"""API route for income statement PDF generation"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from uuid import UUID
from datetime import date
import io

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.services.income_statement_service import income_statement_service

router = APIRouter(prefix="/income-statement", tags=["income-statement"])
logger = get_logger(__name__)


@router.get("/{property_id}/pdf")
async def generate_income_statement_pdf(
    property_id: UUID,
    year: int = Query(default=None, description="Fiscal year (defaults to current year)"),
    current_user: dict = Depends(get_current_user),
):
    """Generate and download an income statement PDF for a property"""
    try:
        if year is None:
            year = date.today().year

        pdf_bytes = income_statement_service.generate_pdf(
            property_id=str(property_id),
            fiscal_year=year,
        )

        filename = f"income_statement_{year}.pdf"

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
