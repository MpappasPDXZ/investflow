"""
Financial Performance API endpoints
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from uuid import UUID
from decimal import Decimal

from app.core.dependencies import get_current_user
from app.schemas.financial_performance import FinancialPerformanceSummary
from app.services.financial_performance_service import financial_performance_service
from app.core.iceberg import read_table, table_exists

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/financial-performance", tags=["financial-performance"])


@router.get("/{property_id}", response_model=FinancialPerformanceSummary)
async def get_financial_performance(
    property_id: UUID,
    unit_id: Optional[UUID] = Query(None, description="Optional unit ID for multi-unit properties"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get financial performance (P&L) for a property or unit
    
    Calculates:
    - Year-to-date rent, expenses (excluding rehab), and profit/loss
    - Cumulative (all-time) rent, expenses, and profit/loss
    - Cash on cash return (if current market value is set)
    """
    try:
        user_id = UUID(current_user["sub"])
        
        # Get property using Iceberg to verify ownership and get values
        if not table_exists(("investflow",), "properties"):
            raise HTTPException(status_code=404, detail="Property not found")
        
        df = read_table(("investflow",), "properties")
        property_df = df[df["id"] == str(property_id)]
        
        if len(property_df) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_dict = property_df.iloc[0].to_dict()
        
        purchase_price = property_dict.get('purchase_price')
        current_market_value = property_dict.get('current_market_value')
        
        # Calculate financial performance
        performance = financial_performance_service.calculate_financial_performance(
            property_id=property_id,
            user_id=user_id,
            unit_id=unit_id,
            purchase_price=Decimal(str(purchase_price)) if purchase_price else None,
            current_market_value=Decimal(str(current_market_value)) if current_market_value else None
        )
        
        return performance
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting financial performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

