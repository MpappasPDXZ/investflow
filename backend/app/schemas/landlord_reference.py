from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from uuid import UUID

class LandlordReferenceBase(BaseModel):
    """Base schema for landlord reference"""
    landlord_name: str = Field(..., max_length=255, description="Name of the landlord or property manager")
    landlord_phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    landlord_email: Optional[str] = Field(None, max_length=255, description="Email address")
    property_address: Optional[str] = Field(None, max_length=500, description="Address of the rental property")
    contact_date: date = Field(..., description="Date the landlord was contacted")
    status: str = Field(..., max_length=50, description="pass, fail, no_info")
    notes: Optional[str] = Field(None, description="Notes from the conversation")


class LandlordReferenceCreate(LandlordReferenceBase):
    """Schema for creating a landlord reference"""
    tenant_id: UUID = Field(..., description="Tenant this reference is for")


class LandlordReferenceUpdate(BaseModel):
    """Schema for updating a landlord reference"""
    landlord_name: Optional[str] = Field(None, max_length=255)
    landlord_phone: Optional[str] = Field(None, max_length=20)
    landlord_email: Optional[str] = Field(None, max_length=255)
    property_address: Optional[str] = Field(None, max_length=500)
    contact_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class LandlordReferenceResponse(LandlordReferenceBase):
    """Schema for landlord reference responses"""
    id: UUID
    tenant_id: UUID
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class LandlordReferenceListResponse(BaseModel):
    """Schema for list of landlord references"""
    references: list[LandlordReferenceResponse]
    total: int
    passed_count: int

