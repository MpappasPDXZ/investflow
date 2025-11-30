"""Pydantic schemas for expense-related API requests and responses"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
import datetime
from uuid import UUID
from decimal import Decimal
from enum import Enum


class ExpenseType(str, Enum):
    """Expense type enum"""
    CAPEX = "capex"
    REHAB = "rehab"  # Initial repairs/renovation to make property rent-ready
    PANDI = "pandi"
    UTILITIES = "utilities"
    MAINTENANCE = "maintenance"
    INSURANCE = "insurance"
    PROPERTY_MANAGEMENT = "property_management"
    OTHER = "other"


class ExpenseBase(BaseModel):
    """Base expense schema with common fields"""
    property_id: UUID = Field(..., description="Property this expense belongs to")
    unit_id: Optional[UUID] = Field(None, description="Optional unit this expense belongs to (for multi-unit properties)")
    description: str = Field(..., max_length=500, description="Description of the expense")
    date: datetime.date = Field(..., description="Date the expense occurred or is planned")
    amount: Decimal = Field(..., ge=0, description="Expense amount")
    vendor: Optional[str] = Field(None, max_length=255, description="Vendor or service provider name")
    expense_type: ExpenseType = Field(..., description="Expense category")
    document_storage_id: Optional[UUID] = Field(None, description="Link to receipt document")
    is_planned: bool = Field(default=False, description="True if planned/future expense, false if actual/receipted")
    notes: Optional[str] = Field(None, description="Additional notes")


class ExpenseCreate(ExpenseBase):
    """Schema for creating a new expense"""
    pass  # created_by_user_id will be added from authenticated user


class ExpenseUpdate(BaseModel):
    """Schema for updating an expense"""
    unit_id: Optional[UUID] = None
    description: Optional[str] = Field(None, max_length=500)
    date: Optional[datetime.date] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    vendor: Optional[str] = Field(None, max_length=255)
    expense_type: Optional[ExpenseType] = None
    document_storage_id: Optional[UUID] = None
    is_planned: Optional[bool] = None
    notes: Optional[str] = None


class ExpenseResponse(ExpenseBase):
    """Schema for expense response"""
    id: UUID
    unit_id: Optional[UUID] = None
    created_by_user_id: Optional[UUID] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class ExpenseListResponse(BaseModel):
    """Schema for paginated expense list response"""
    items: list[ExpenseResponse]
    total: int
    page: int
    limit: int


class YearlyExpenseTotal(BaseModel):
    """Schema for yearly expense totals"""
    year: int
    total: float
    count: int
    by_type: dict[str, float]


class ExpenseSummaryResponse(BaseModel):
    """Schema for expense summary with yearly subtotals"""
    yearly_totals: list[YearlyExpenseTotal]
    type_totals: dict[str, float]
    grand_total: float
    total_count: int

