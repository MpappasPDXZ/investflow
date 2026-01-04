"""Pydantic schemas for tenant-related API requests and responses"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
import json


class TenantBase(BaseModel):
    """
    Base tenant schema with fields ordered to match Iceberg schema column order.
    Fields are grouped by type: string, decimal128, int32, date32, boolean, timestamp
    """
    # STRING fields (in Iceberg order)
    property_id: UUID = Field(..., description="Property ID (required)")
    unit_id: Optional[UUID] = Field(None, description="Unit ID (optional, for multi-family)")
    first_name: str = Field(..., max_length=100, description="Tenant first name")
    last_name: str = Field(..., max_length=100, description="Tenant last name")
    email: Optional[EmailStr] = Field(None, description="Tenant email address")
    phone: Optional[str] = Field(None, max_length=20, description="Primary phone number")
    current_address: Optional[str] = Field(None, max_length=255, description="Current street address")
    current_city: Optional[str] = Field(None, max_length=100, description="Current city")
    current_state: Optional[str] = Field(None, max_length=2, description="Current state")
    current_zip: Optional[str] = Field(None, max_length=10, description="Current ZIP code")
    employer_name: Optional[str] = Field(None, max_length=255, description="Current employer")
    status: Optional[str] = Field("applicant", max_length=50, description="Status: applicant, approved, current, former, rejected")
    notes: Optional[str] = Field(None, description="Internal notes about tenant")
    background_check_status: Optional[str] = Field(None, max_length=50, description="pass, fail, pending, not_started")
    
    # DECIMAL128 fields (in Iceberg order)
    monthly_income: Optional[Decimal] = Field(None, ge=0, description="Monthly gross income")
    
    # INT32 fields (in Iceberg order)
    credit_score: Optional[int] = Field(None, ge=300, le=850, description="Credit score if available")
    
    # DATE32 fields (in Iceberg order)
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    
    # JSON fields (stored as string in Iceberg)
    landlord_references: Optional[List[Dict[str, Any]]] = Field(None, description="Landlord references stored as JSON array")


class TenantCreate(TenantBase):
    """Schema for creating a new tenant"""
    pass


class TenantUpdate(BaseModel):
    """Schema for updating tenant information - all fields optional for partial updates"""
    # STRING fields (in Iceberg order)
    property_id: Optional[UUID] = Field(None, description="Property ID")
    unit_id: Optional[UUID] = Field(None, description="Unit ID")
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    current_address: Optional[str] = Field(None, max_length=255)
    current_city: Optional[str] = Field(None, max_length=100)
    current_state: Optional[str] = Field(None, max_length=2)
    current_zip: Optional[str] = Field(None, max_length=10)
    employer_name: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    background_check_status: Optional[str] = Field(None, max_length=50)
    
    # DECIMAL128 fields (in Iceberg order)
    monthly_income: Optional[Decimal] = Field(None, ge=0)
    
    # INT32 fields (in Iceberg order)
    credit_score: Optional[int] = Field(None, ge=300, le=850)
    
    # DATE32 fields (in Iceberg order)
    date_of_birth: Optional[date] = None
    
    # JSON fields (stored as string in Iceberg)
    landlord_references: Optional[List[Dict[str, Any]]] = None


class TenantResponse(TenantBase):
    """Schema for tenant responses"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_dict(cls, data: dict):
        """Convert dict to TenantResponse, handling JSON fields"""
        # Parse landlord_references JSON string if present
        if 'landlord_references' in data and isinstance(data['landlord_references'], str):
            try:
                data['landlord_references'] = json.loads(data['landlord_references']) if data['landlord_references'] else []
            except (json.JSONDecodeError, TypeError):
                data['landlord_references'] = []
        elif 'landlord_references' not in data:
            data['landlord_references'] = []
        
        return cls(**data)


class TenantListResponse(BaseModel):
    """Schema for list of tenants"""
    tenants: list[TenantResponse]
    total: int
