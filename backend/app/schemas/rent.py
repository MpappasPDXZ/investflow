"""Pydantic schemas for rent-related API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import date
from uuid import UUID
from decimal import Decimal


class RentBase(BaseModel):
    """Base rent schema with common fields"""
    property_id: UUID = Field(..., description="Property ID")
    unit_id: Optional[UUID] = Field(None, description="Unit ID (for multi-unit properties)")
    client_id: Optional[UUID] = Field(None, description="Client/Tenant ID")
    amount: Decimal = Field(..., ge=0, description="Rent amount")
    rent_period_month: int = Field(..., ge=1, le=12, description="Month the rent is for (1-12)")
    rent_period_year: int = Field(..., ge=2000, le=2100, description="Year the rent is for")
    payment_date: date = Field(..., description="Date the rent was paid")
    payment_method: Optional[Literal["check", "cash", "electronic", "money_order", "other"]] = Field(
        None, description="Payment method"
    )
    transaction_reference: Optional[str] = Field(None, max_length=255, description="Check #, transaction ID, etc.")
    is_late: bool = Field(False, description="Whether payment was late")
    late_fee: Optional[Decimal] = Field(None, ge=0, description="Late fee amount if applicable")
    notes: Optional[str] = Field(None, description="Additional notes")


class RentCreate(RentBase):
    """Schema for creating a new rent payment"""
    pass


class RentUpdate(BaseModel):
    """Schema for updating an existing rent payment"""
    amount: Optional[Decimal] = Field(None, ge=0)
    rent_period_month: Optional[int] = Field(None, ge=1, le=12)
    rent_period_year: Optional[int] = Field(None, ge=2000, le=2100)
    payment_date: Optional[date] = None
    payment_method: Optional[Literal["check", "cash", "electronic", "money_order", "other"]] = None
    transaction_reference: Optional[str] = Field(None, max_length=255)
    is_late: Optional[bool] = None
    late_fee: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None


class RentResponse(BaseModel):
    """Schema for rent response"""
    id: UUID
    property_id: UUID
    unit_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    amount: Decimal
    rent_period_month: int
    rent_period_year: int
    rent_period_start: date
    rent_period_end: date
    payment_date: date
    payment_method: Optional[str] = None
    transaction_reference: Optional[str] = None
    is_late: bool
    late_fee: Optional[Decimal] = None
    notes: Optional[str] = None
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





