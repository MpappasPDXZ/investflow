"""
Pydantic schemas for scheduled expenses and revenue
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from decimal import Decimal
from datetime import datetime


# ========== SCHEDULED EXPENSES ==========

class ScheduledExpenseBase(BaseModel):
    """Base schema for scheduled expenses"""
    property_id: str
    expense_type: str  # 'capex', 'pti', 'pi', 'maintenance', 'vacancy'
    item_name: str
    
    # CapEx fields
    purchase_price: Optional[Decimal] = None
    depreciation_rate: Optional[Decimal] = None
    count: Optional[int] = None
    
    # PTI fields (also used by Maintenance)
    annual_cost: Optional[Decimal] = None
    
    # P&I fields
    principal: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    
    notes: Optional[str] = None


class ScheduledExpenseCreate(ScheduledExpenseBase):
    """Schema for creating a scheduled expense"""
    pass


class ScheduledExpenseUpdate(BaseModel):
    """Schema for updating a scheduled expense"""
    item_name: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    depreciation_rate: Optional[Decimal] = None
    count: Optional[int] = None
    annual_cost: Optional[Decimal] = None
    principal: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ScheduledExpenseResponse(ScheduledExpenseBase):
    """Schema for scheduled expense response"""
    model_config = ConfigDict(json_encoders={Decimal: float})
    
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    calculated_annual_cost: Optional[Decimal] = None  # Computed field


class ScheduledExpenseListResponse(BaseModel):
    """Schema for list of scheduled expenses"""
    items: list[ScheduledExpenseResponse]
    total: int


# ========== SCHEDULED REVENUE ==========

class ScheduledRevenueBase(BaseModel):
    """Base schema for scheduled revenue"""
    property_id: str
    revenue_type: str  # 'principal_paydown', 'appreciation', 'value_added', 'tax_savings'
    item_name: str
    
    # Principal Paydown fields
    annual_amount: Optional[Decimal] = None
    
    # Appreciation fields
    appreciation_rate: Optional[Decimal] = None
    property_value: Optional[Decimal] = None
    
    # Value Added fields
    value_added_amount: Optional[Decimal] = None
    
    notes: Optional[str] = None


class ScheduledRevenueCreate(ScheduledRevenueBase):
    """Schema for creating scheduled revenue"""
    pass


class ScheduledRevenueUpdate(BaseModel):
    """Schema for updating scheduled revenue"""
    item_name: Optional[str] = None
    annual_amount: Optional[Decimal] = None
    appreciation_rate: Optional[Decimal] = None
    property_value: Optional[Decimal] = None
    value_added_amount: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ScheduledRevenueResponse(ScheduledRevenueBase):
    """Schema for scheduled revenue response"""
    model_config = ConfigDict(json_encoders={Decimal: float})
    
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    calculated_annual_amount: Optional[Decimal] = None  # Computed field


class ScheduledRevenueListResponse(BaseModel):
    """Schema for list of scheduled revenue"""
    items: list[ScheduledRevenueResponse]
    total: int

