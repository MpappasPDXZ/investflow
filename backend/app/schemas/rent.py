"""Pydantic schemas for rent-related API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Union
from datetime import date
from uuid import UUID
from decimal import Decimal


class RentBase(BaseModel):
    """Base rent schema with common fields"""
    property_id: UUID = Field(..., description="Property ID")
    unit_id: Optional[UUID] = Field(None, description="Unit ID (for multi-unit properties)")
    tenant_id: Optional[UUID] = Field(None, description="Tenant ID (optional)")
    amount: Decimal = Field(..., description="Rent amount (can be negative for deposit payouts/deductions)")
    revenue_description: Optional[str] = Field(None, max_length=255, description="Description of revenue type (Monthly Rent, Partial Month Rent, One Time Pet Fee, One Time Application Fee, Deposit, Other)")
    is_non_irs_revenue: bool = Field(False, description="Whether this is non-IRS revenue (e.g., deposits that don't count toward revenue vs cost)")
    is_one_time_fee: bool = Field(False, description="Whether this is a one-time fee (e.g., pet fee, application fee)")
    rent_period_month: Optional[int] = Field(None, ge=1, le=12, description="Month the rent is for (1-12) - required if not one-time fee")
    rent_period_year: Optional[int] = Field(None, ge=2000, le=2100, description="Year the rent is for - required if not one-time fee")
    rent_period_start: Optional[date] = Field(None, description="Rent period start date (defaults to month start if not provided, or single date for one-time fee)")
    rent_period_end: Optional[date] = Field(None, description="Rent period end date (defaults to month end if not provided, or same as start for one-time fee)")
    payment_date: date = Field(..., description="Date the rent was paid")
    payment_method: Optional[Literal["check", "cash", "electronic", "money_order", "other"]] = Field(
        None, description="Payment method"
    )
    transaction_reference: Optional[str] = Field(None, max_length=255, description="Check #, transaction ID, etc.")
    is_late: bool = Field(False, description="Whether payment was late")
    late_fee: Optional[Decimal] = Field(None, ge=0, description="Late fee amount if applicable")
    notes: Optional[str] = Field(None, description="Additional notes")
    document_storage_id: Optional[UUID] = Field(None, description="Document storage ID for receipt/image")


class RentCreate(RentBase):
    """Schema for creating a new rent payment"""
    pass


class RentUpdate(BaseModel):
    """Schema for updating an existing rent payment"""
    property_id: Optional[UUID] = Field(None, description="Property ID")
    unit_id: Optional[UUID] = Field(None, description="Unit ID (for multi-unit properties)")
    tenant_id: Optional[UUID] = Field(None, description="Tenant ID (optional)")
    amount: Optional[Decimal] = Field(None, description="Rent amount (can be negative for deposit payouts/deductions)")
    revenue_description: Optional[str] = Field(None, max_length=255, description="Description of revenue type")
    is_non_irs_revenue: Optional[bool] = Field(None, description="Whether this is non-IRS revenue")
    is_one_time_fee: Optional[bool] = Field(None, description="Whether this is a one-time fee")
    rent_period_month: Optional[int] = Field(None, ge=1, le=12, description="Month the rent is for (1-12)")
    rent_period_year: Optional[int] = Field(None, ge=2000, le=2100, description="Year the rent is for")
    rent_period_start: Optional[date] = Field(None, description="Rent period start date")
    rent_period_end: Optional[date] = Field(None, description="Rent period end date")
    payment_date: Optional[date] = Field(None, description="Date the rent was paid")
    payment_method: Optional[Literal["check", "cash", "electronic", "money_order", "other"]] = Field(None, description="Payment method")
    transaction_reference: Optional[str] = Field(None, max_length=255, description="Check #, transaction ID, etc.")
    is_late: Optional[bool] = Field(None, description="Whether payment was late")
    late_fee: Optional[Decimal] = Field(None, ge=0, description="Late fee amount if applicable")
    notes: Optional[str] = Field(None, description="Additional notes")
    document_storage_id: Optional[Union[UUID, str]] = Field(None, description="Document storage ID for receipt/image (or empty string '' to delete existing document)")


class RentResponse(BaseModel):
    """Schema for rent response with denormalized fields (ordered by dtype to match Iceberg schema)"""
    # STRING fields (in Iceberg order)
    id: UUID
    property_id: UUID
    property_name: Optional[str] = None
    unit_id: Optional[UUID] = None
    unit_name: Optional[str] = None
    tenant_id: Optional[UUID] = None
    tenant_name: Optional[str] = None
    revenue_description: Optional[str] = None
    payment_method: Optional[str] = None
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    document_storage_id: Optional[UUID] = None
    created_by_user_id: Optional[UUID] = None
    
    # DECIMAL128 fields (in Iceberg order)
    amount: Decimal
    late_fee: Optional[Decimal] = None
    
    # INT32 fields (in Iceberg order)
    rent_period_month: Optional[int] = None
    rent_period_year: Optional[int] = None
    
    # DATE32 fields (in Iceberg order)
    rent_period_start: date
    rent_period_end: date
    payment_date: date
    
    # BOOLEAN fields (in Iceberg order)
    is_non_irs_revenue: bool
    is_one_time_fee: bool
    is_late: bool
    
    # TIMESTAMP fields (in Iceberg order)
    created_at: Optional[date] = None
    updated_at: Optional[date] = None

    class Config:
        from_attributes = True


class RentListResponse(BaseModel):
    """Schema for paginated rent list response"""
    items: List[RentResponse]
    total: int
    page: int
    limit: int










