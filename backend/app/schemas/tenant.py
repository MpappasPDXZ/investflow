from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

class TenantBase(BaseModel):
    """Base schema for tenant information"""
    # Personal Information
    first_name: str = Field(..., max_length=100, description="Tenant first name")
    last_name: str = Field(..., max_length=100, description="Tenant last name")
    email: Optional[EmailStr] = Field(None, description="Tenant email address")
    phone: Optional[str] = Field(None, max_length=20, description="Primary phone number")
    phone_secondary: Optional[str] = Field(None, max_length=20, description="Secondary phone number")
    
    # Identification
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    ssn_last_four: Optional[str] = Field(None, max_length=4, description="Last 4 digits of SSN (for identification)")
    drivers_license: Optional[str] = Field(None, max_length=50, description="Driver's license number")
    drivers_license_state: Optional[str] = Field(None, max_length=2, description="DL state (e.g., NE, MO)")
    
    # Current Address
    current_address: Optional[str] = Field(None, max_length=255, description="Current street address")
    current_city: Optional[str] = Field(None, max_length=100, description="Current city")
    current_state: Optional[str] = Field(None, max_length=2, description="Current state")
    current_zip: Optional[str] = Field(None, max_length=10, description="Current ZIP code")
    
    # Employment
    employer_name: Optional[str] = Field(None, max_length=255, description="Current employer")
    employer_phone: Optional[str] = Field(None, max_length=20, description="Employer phone")
    job_title: Optional[str] = Field(None, max_length=100, description="Job title/position")
    monthly_income: Optional[Decimal] = Field(None, ge=0, description="Monthly gross income")
    employment_start_date: Optional[date] = Field(None, description="Employment start date")
    
    # Emergency Contact
    emergency_contact_name: Optional[str] = Field(None, max_length=100, description="Emergency contact name")
    emergency_contact_phone: Optional[str] = Field(None, max_length=20, description="Emergency contact phone")
    emergency_contact_relationship: Optional[str] = Field(None, max_length=50, description="Relationship to tenant")
    
    # Screening Documents (stored in vault, referenced by document_id)
    background_check_document_id: Optional[str] = Field(None, description="Background check document ID from vault")
    application_document_id: Optional[str] = Field(None, description="Rental application document ID from vault")
    
    # Status
    status: Optional[str] = Field("applicant", max_length=50, description="Status: applicant, approved, current, former, rejected")
    notes: Optional[str] = Field(None, description="Internal notes about tenant")
    
    # Screening Results
    background_check_date: Optional[date] = Field(None, description="Date background check was completed")
    background_check_status: Optional[str] = Field(None, max_length=50, description="pass, fail, pending, not_started")
    credit_score: Optional[int] = Field(None, ge=300, le=850, description="Credit score if available")
    
    # Rental History
    has_evictions: Optional[bool] = Field(None, description="Has the tenant been evicted before?")
    eviction_details: Optional[str] = Field(None, description="Details about any evictions")
    
    # Lease Assignment (optional - can be set later)
    property_id: Optional[UUID] = Field(None, description="Property ID if assigned to property/unit")
    unit_id: Optional[UUID] = Field(None, description="Unit ID if assigned to specific unit")
    lease_id: Optional[UUID] = Field(None, description="Active lease ID if tenant is signed")


class TenantCreate(TenantBase):
    """Schema for creating a new tenant"""
    pass


class TenantUpdate(BaseModel):
    """Schema for updating tenant information"""
    # All fields optional for partial updates
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    
    date_of_birth: Optional[date] = None
    ssn_last_four: Optional[str] = Field(None, max_length=4)
    drivers_license: Optional[str] = Field(None, max_length=50)
    drivers_license_state: Optional[str] = Field(None, max_length=2)
    
    current_address: Optional[str] = Field(None, max_length=255)
    current_city: Optional[str] = Field(None, max_length=100)
    current_state: Optional[str] = Field(None, max_length=2)
    current_zip: Optional[str] = Field(None, max_length=10)
    
    employer_name: Optional[str] = Field(None, max_length=255)
    employer_phone: Optional[str] = Field(None, max_length=20)
    job_title: Optional[str] = Field(None, max_length=100)
    monthly_income: Optional[Decimal] = Field(None, ge=0)
    employment_start_date: Optional[date] = None
    
    emergency_contact_name: Optional[str] = Field(None, max_length=100)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=50)
    
    background_check_document_id: Optional[str] = None
    application_document_id: Optional[str] = None
    
    status: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    
    background_check_date: Optional[date] = None
    background_check_status: Optional[str] = Field(None, max_length=50)
    credit_score: Optional[int] = Field(None, ge=300, le=850)
    
    property_id: Optional[UUID] = None
    unit_id: Optional[UUID] = None
    lease_id: Optional[UUID] = None


class TenantResponse(TenantBase):
    """Schema for tenant responses"""
    id: UUID
    user_id: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    landlord_references_passed: int = 0  # Count of passed landlord references
    
    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    """Schema for list of tenants"""
    tenants: list[TenantResponse]
    total: int

