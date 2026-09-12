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
    PANDI = "pandi" # Principal pay down is not an expense.  Interest and escrow are.
    TAX = "tax"  # Property taxes
    UTILITIES = "utilities"
    MAINTENANCE = "maintenance"
    INSURANCE = "insurance"
    PROPERTY_MANAGEMENT = "property_management"
    OTHER = "other"


class ExpenseCategory(str, Enum):
    """Expense category enum - numbered cost code categories for sorting"""
    CO_EQUIP = "co_equip"           # 10 - Company Equipment
    RENT_EQUIP = "rent_equip"       # 20 - Rented Equipment
    EQUIP_MAINT = "equip_maint"     # 30 - Equipment Maintenance
    SMALL_TOOLS = "small_tools"     # 40 - Small Tools
    BULK_COMM = "bulk_comm"         # 50 - Bulk Commodities (default)
    ENG_EQUIP = "eng_equip"         # 60 - Engineered Equipment
    SUBS = "subs"                   # 70 - Subcontractors
    OTHER = "other"                 # 80 - Other


class TaxCategory(str, Enum):
    """IRS Schedule E line item categories for rental property expenses"""
    ADVERTISING = "advertising"                 # Line 5
    AUTO_TRAVEL = "auto_travel"                 # Line 6
    CLEANING = "cleaning"                       # Line 7
    COMMISSIONS = "commissions"                 # Line 8
    INSURANCE = "insurance"                     # Line 9
    LEGAL_PROFESSIONAL = "legal_professional"   # Line 10
    MANAGEMENT_FEES = "management_fees"         # Line 11
    MORTGAGE_INTEREST = "mortgage_interest"     # Line 12
    OTHER_INTEREST = "other_interest"           # Line 13
    REPAIRS = "repairs"                         # Line 14 (default)
    SUPPLIES = "supplies"                       # Line 15
    TAXES = "taxes"                             # Line 16
    UTILITIES = "utilities"                     # Line 17
    CAPITAL_IMPROVEMENT = "capital_improvement" # Line 18 - Depreciation
    OTHER = "other"                             # Line 19


class ExpenseBase(BaseModel):
    """
    Base expense schema with fields ordered to match Iceberg schema column order.
    Fields are grouped by type: string, decimal128, date32, boolean, timestamp
    """
    # STRING fields (in Iceberg order)
    property_id: UUID = Field(..., description="Property this expense belongs to")
    unit_id: Optional[UUID] = Field(None, description="Optional unit this expense belongs to")
    description: str = Field(..., max_length=500, description="Description of the expense")
    vendor: Optional[str] = Field(None, max_length=255, description="Vendor or service provider name")
    expense_type: ExpenseType = Field(..., description="Expense type")
    expense_category: Optional[ExpenseCategory] = Field(None, description="Cost code category")
    tax_category: Optional[TaxCategory] = Field(None, description="IRS Schedule E tax classification")
    document_storage_id: Optional[UUID] = Field(None, description="Link to receipt document")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # DECIMAL128 fields (in Iceberg order)
    amount: Decimal = Field(..., ge=0, description="Expense amount (decimal128)")
    
    # DATE32 fields (in Iceberg order)
    date: datetime.date = Field(..., description="Date the expense occurred (date32)")
    
    # BOOLEAN fields (in Iceberg order)
    has_receipt: Optional[bool] = Field(None, description="Whether the expense has a receipt attached")


class ExpenseCreate(ExpenseBase):
    """Schema for creating a new expense"""
    pass


class ExpenseUpdate(BaseModel):
    """Schema for updating an expense - fields ordered by Iceberg type"""
    # STRING fields
    unit_id: Optional[UUID] = None
    description: Optional[str] = Field(None, max_length=500)
    vendor: Optional[str] = Field(None, max_length=255)
    expense_type: Optional[ExpenseType] = None
    expense_category: Optional[ExpenseCategory] = None
    tax_category: Optional[TaxCategory] = None
    document_storage_id: Optional[UUID] = None
    notes: Optional[str] = None
    
    # DECIMAL128 fields
    amount: Optional[Decimal] = Field(None, ge=0)
    
    # DATE32 fields
    date: Optional[datetime.date] = None
    
    # BOOLEAN fields
    has_receipt: Optional[bool] = None


class ExpenseResponse(ExpenseBase):
    """
    Schema for expense response - includes system fields in Iceberg order.
    Fields ordered: ExpenseBase fields + id (string), created_at, updated_at (timestamp)
    """
    # System fields (in Iceberg order)
    id: UUID  # string in Iceberg
    created_at: datetime.datetime  # timestamp in Iceberg
    updated_at: datetime.datetime  # timestamp in Iceberg

    class Config:
        from_attributes = True

    @classmethod
    def from_expense(cls, exp: dict) -> "ExpenseResponse":
        """Nan-safe constructor for pandas/Postgres rows."""
        import pandas as pd
        from typing import Any

        def _none_if_null(value: Any) -> Any:
            if value is None:
                return None
            try:
                if pd.isna(value):
                    return None
            except Exception:
                pass
            if value == "" or value == "None" or value == "nan" or value == "NaT":
                return None
            return value

        has_receipt = _none_if_null(exp.get("has_receipt"))
        doc_id = _none_if_null(exp.get("document_storage_id"))
        if has_receipt is None:
            has_receipt = doc_id is not None
        else:
            has_receipt = bool(has_receipt)

        raw_date = _none_if_null(exp.get("date"))
        if raw_date is None:
            created = _none_if_null(exp.get("created_at"))
            raw_date = pd.Timestamp(created).date() if created is not None else datetime.date(1970, 1, 1)
        elif hasattr(raw_date, "date") and not isinstance(raw_date, datetime.date):
            raw_date = raw_date.date()

        created_at = exp.get("created_at")
        updated_at = exp.get("updated_at")
        if created_at is not None and not isinstance(created_at, datetime.datetime):
            created_at = pd.Timestamp(created_at).to_pydatetime()
        if updated_at is not None and not isinstance(updated_at, datetime.datetime):
            updated_at = pd.Timestamp(updated_at).to_pydatetime()

        return cls(
            id=exp["id"],
            property_id=exp["property_id"],
            unit_id=_none_if_null(exp.get("unit_id")),
            description=exp["description"],
            vendor=_none_if_null(exp.get("vendor")),
            expense_type=exp["expense_type"],
            expense_category=_none_if_null(exp.get("expense_category")),
            tax_category=_none_if_null(exp.get("tax_category")),
            document_storage_id=doc_id,
            notes=_none_if_null(exp.get("notes")),
            amount=exp["amount"],
            date=raw_date,
            has_receipt=has_receipt,
            created_at=created_at,
            updated_at=updated_at,
        )


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
    by_tax_category: dict[str, float] = {}


class ExpenseSummaryResponse(BaseModel):
    """Schema for expense summary with yearly subtotals"""
    yearly_totals: list[YearlyExpenseTotal]
    type_totals: dict[str, float]
    tax_category_totals: dict[str, float] = {}
    grand_total: float
    total_count: int

