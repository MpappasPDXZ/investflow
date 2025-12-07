"""Pydantic schemas for financial performance (profit/loss) calculations and caching"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from uuid import UUID
from decimal import Decimal


class FinancialPerformanceBase(BaseModel):
    """Base schema for cached financial performance"""
    property_id: UUID = Field(..., description="Property ID")
    unit_id: Optional[UUID] = Field(None, description="Optional unit ID for multi-unit properties")
    
    # Year-to-date calculations
    ytd_rent: Decimal = Field(default=Decimal("0"), description="Year-to-date rent collected")
    ytd_expenses: Decimal = Field(default=Decimal("0"), description="Year-to-date non-rehab expenses")
    ytd_profit_loss: Decimal = Field(default=Decimal("0"), description="Year-to-date profit/loss (rent - expenses)")
    
    # Cumulative (all-time) calculations
    cumulative_rent: Decimal = Field(default=Decimal("0"), description="All-time rent collected")
    cumulative_expenses: Decimal = Field(default=Decimal("0"), description="All-time non-rehab expenses")
    cumulative_profit_loss: Decimal = Field(default=Decimal("0"), description="All-time profit/loss")
    
    # Cash on cash calculation
    current_market_value: Optional[Decimal] = Field(None, description="Current market value")
    purchase_price: Decimal = Field(default=Decimal("0"), description="Purchase price")
    cash_on_cash: Optional[Decimal] = Field(None, description="(Current Value - Purchase Price) / Purchase Price")
    
    last_calculated_at: date = Field(..., description="When this was last calculated")


class FinancialPerformanceResponse(FinancialPerformanceBase):
    """Schema for financial performance response"""
    id: UUID
    created_at: date
    updated_at: date
    
    class Config:
        from_attributes = True


class FinancialPerformanceSummary(BaseModel):
    """Aggregated summary for display"""
    property_id: UUID
    
    # YTD aggregates (property-level sum)
    ytd_rent: Decimal
    ytd_expenses: Decimal
    ytd_profit_loss: Decimal
    
    # YTD expense breakdown by type
    ytd_piti: Decimal = Decimal("0")  # Principal, Interest, Tax, Insurance
    ytd_utilities: Decimal = Decimal("0")
    ytd_maintenance: Decimal = Decimal("0")
    ytd_capex: Decimal = Decimal("0")
    ytd_insurance: Decimal = Decimal("0")
    ytd_property_management: Decimal = Decimal("0")
    ytd_other: Decimal = Decimal("0")
    
    # Cumulative aggregates
    cumulative_rent: Decimal
    cumulative_expenses: Decimal
    cumulative_profit_loss: Decimal
    
    # Cumulative expense breakdown by type
    cumulative_piti: Decimal = Decimal("0")
    cumulative_utilities: Decimal = Decimal("0")
    cumulative_maintenance: Decimal = Decimal("0")
    cumulative_capex: Decimal = Decimal("0")
    cumulative_insurance: Decimal = Decimal("0")
    cumulative_property_management: Decimal = Decimal("0")
    cumulative_other: Decimal = Decimal("0")
    
    # Cash on cash
    cash_on_cash: Optional[Decimal] = None
    
    # Unit-level breakdowns (if multi-unit)
    units: Optional[list[dict]] = None
    
    last_calculated_at: date

