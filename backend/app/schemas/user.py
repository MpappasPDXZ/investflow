"""Pydantic schemas for user-related API requests and responses"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema with common fields"""
    first_name: str = Field(..., max_length=100, description="First name")
    last_name: str = Field(..., max_length=100, description="Last name")
    email: EmailStr = Field(..., description="Email address")
    tax_rate: Optional[float] = Field(None, ge=0, le=1, description="Tax rate as decimal (e.g., 0.22 for 22%)")
    mortgage_interest_rate: Optional[float] = Field(None, ge=0, le=1, description="30-year mortgage interest rate as decimal (e.g., 0.07 for 7%)")
    loc_interest_rate: Optional[float] = Field(None, ge=0, le=1, description="Line of Credit interest rate as decimal (e.g., 0.07 for 7%)")


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class UserUpdate(BaseModel):
    """Schema for updating user profile"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    tax_rate: Optional[float] = Field(None, ge=0, le=1)
    mortgage_interest_rate: Optional[float] = Field(None, ge=0, le=1)
    loc_interest_rate: Optional[float] = Field(None, ge=0, le=1)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response (excludes password)"""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

