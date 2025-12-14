"""Pydantic schemas for lease management"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
import json


class MoveOutCostItem(BaseModel):
    """Individual move-out cost item"""
    item: str = Field(..., description="Name of the cost item")
    description: Optional[str] = Field(None, description="Detailed description")
    amount: Decimal = Field(..., gt=0, description="Cost amount")
    order: int = Field(..., ge=1, description="Display order")


class TenantBase(BaseModel):
    """Base tenant model"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


class TenantCreate(TenantBase):
    """Tenant creation (no IDs needed)"""
    pass


class TenantUpdate(BaseModel):
    """Tenant update (all fields optional)"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    signed_date: Optional[date] = None


class TenantResponse(TenantBase):
    """Tenant response"""
    id: UUID
    lease_id: UUID
    tenant_order: int
    signed_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeaseBase(BaseModel):
    """Base lease model with common fields"""
    # Property/Unit
    property_id: UUID
    unit_id: Optional[UUID] = None
    
    # Status & State
    state: str = Field(..., pattern="^(NE|MO)$", description="State code: NE or MO")
    status: Optional[str] = Field("draft", pattern="^(draft|pending_signature|active|expired|terminated)$")
    
    # Dates
    commencement_date: date
    termination_date: date
    auto_convert_month_to_month: Optional[bool] = False
    lease_date: Optional[date] = None
    
    # Financial Terms
    monthly_rent: Decimal = Field(..., gt=0, description="Monthly rent amount")
    rent_due_day: Optional[int] = Field(1, ge=1, le=31)
    rent_due_by_day: Optional[int] = Field(5, ge=1, le=31)
    rent_due_by_time: Optional[str] = Field("6pm", max_length=20)
    payment_method: Optional[str] = Field(None, max_length=100)
    prorated_first_month_rent: Optional[Decimal] = Field(None, ge=0)
    
    # Late Charges
    late_fee_day_1_10: Optional[Decimal] = Field(None, ge=0)
    late_fee_day_11: Optional[Decimal] = Field(None, ge=0)
    late_fee_day_16: Optional[Decimal] = Field(None, ge=0)
    late_fee_day_21: Optional[Decimal] = Field(None, ge=0)
    
    # NSF Fee
    nsf_fee: Optional[Decimal] = Field(None, ge=0)
    
    # Security Deposit
    security_deposit: Decimal = Field(..., ge=0)
    deposit_return_days: Optional[int] = Field(None, ge=1)
    
    # Occupants
    max_occupants: Optional[int] = Field(3, ge=1)
    max_adults: Optional[int] = Field(2, ge=1)
    max_children: Optional[bool] = True
    
    # Utilities
    utilities_tenant: Optional[str] = Field(None, max_length=500)
    utilities_landlord: Optional[str] = Field(None, max_length=500)
    
    # Pets
    pets_allowed: Optional[bool] = True
    pet_fee_one: Optional[Decimal] = Field(None, ge=0)
    pet_fee_two: Optional[Decimal] = Field(None, ge=0)
    max_pets: Optional[int] = Field(2, ge=0)
    
    # Parking
    parking_spaces: Optional[int] = Field(2, ge=0)
    parking_small_vehicles: Optional[int] = Field(2, ge=0)
    parking_large_trucks: Optional[int] = Field(1, ge=0)
    
    # Keys
    front_door_keys: Optional[int] = Field(1, ge=0)
    back_door_keys: Optional[int] = Field(1, ge=0)
    key_replacement_fee: Optional[Decimal] = Field(None, ge=0)
    
    # Shared Driveway
    has_shared_driveway: Optional[bool] = False
    shared_driveway_with: Optional[str] = Field(None, max_length=200)
    snow_removal_responsibility: Optional[str] = Field("tenant", max_length=50)
    
    # Garage
    has_garage: Optional[bool] = False
    garage_outlets_prohibited: Optional[bool] = False
    
    # Special Spaces
    has_attic: Optional[bool] = False
    attic_usage: Optional[str] = Field(None, max_length=500)
    has_basement: Optional[bool] = False
    
    # Appliances
    appliances_provided: Optional[str] = Field(None, max_length=1000)
    
    # Lead Paint
    lead_paint_disclosure: Optional[bool] = True
    lead_paint_year_built: Optional[int] = Field(None, ge=1800, le=2100)
    
    # Early Termination
    early_termination_allowed: Optional[bool] = True
    early_termination_notice_days: Optional[int] = Field(60, ge=0)
    early_termination_fee_months: Optional[int] = Field(2, ge=0)
    early_termination_fee_amount: Optional[Decimal] = Field(None, ge=0)
    
    # Move-Out Costs (as JSON-compatible list)
    moveout_costs: Optional[List[MoveOutCostItem]] = None
    
    # Missouri-Specific
    methamphetamine_disclosure: Optional[bool] = None
    owner_name: Optional[str] = Field(None, max_length=200)
    owner_address: Optional[str] = Field(None, max_length=500)
    manager_name: Optional[str] = Field(None, max_length=200)
    manager_address: Optional[str] = Field(None, max_length=500)
    deposit_account_info: Optional[str] = Field(None, max_length=500)
    moveout_inspection_rights: Optional[bool] = None
    military_termination_days: Optional[int] = Field(None, ge=0)
    
    # Notes
    notes: Optional[str] = None
    
    @field_validator('termination_date')
    @classmethod
    def validate_termination_date(cls, v, info):
        """Ensure termination date is after commencement date"""
        if 'commencement_date' in info.data and v <= info.data['commencement_date']:
            raise ValueError('Termination date must be after commencement date')
        return v
    
    @model_validator(mode='after')
    def validate_state_specific_fields(self):
        """Validate state-specific required fields"""
        if self.state == 'MO':
            if self.methamphetamine_disclosure is None:
                raise ValueError('Methamphetamine disclosure is required for Missouri leases')
            if not self.owner_name:
                raise ValueError('Owner name is required for Missouri leases')
            if not self.owner_address:
                raise ValueError('Owner address is required for Missouri leases')
            if self.moveout_inspection_rights is None:
                raise ValueError('Move-out inspection rights must be specified for Missouri leases')
        
        return self
    
    @field_validator('security_deposit')
    @classmethod
    def validate_security_deposit(cls, v, info):
        """Validate security deposit limits based on state"""
        if 'monthly_rent' not in info.data or 'state' not in info.data:
            return v
        
        monthly_rent = info.data['monthly_rent']
        state = info.data['state']
        
        if state == 'NE' and v > monthly_rent:
            raise ValueError('Nebraska: Security deposit cannot exceed 1 month rent')
        elif state == 'MO' and v > (monthly_rent * 2):
            raise ValueError('Missouri: Security deposit cannot exceed 2 months rent')
        
        return v


class LeaseCreate(LeaseBase):
    """Lease creation with tenants"""
    tenants: List[TenantCreate] = Field(..., min_length=1, description="At least one tenant required")


class LeaseUpdate(BaseModel):
    """Lease update (all fields optional except cannot change property/state)"""
    # Dates
    commencement_date: Optional[date] = None
    termination_date: Optional[date] = None
    auto_convert_month_to_month: Optional[bool] = None
    lease_date: Optional[date] = None
    
    # Financial Terms
    monthly_rent: Optional[Decimal] = Field(None, gt=0)
    rent_due_day: Optional[int] = Field(None, ge=1, le=31)
    rent_due_by_day: Optional[int] = Field(None, ge=1, le=31)
    rent_due_by_time: Optional[str] = Field(None, max_length=20)
    payment_method: Optional[str] = Field(None, max_length=100)
    prorated_first_month_rent: Optional[Decimal] = Field(None, ge=0)
    
    # Late Charges
    late_fee_day_1_10: Optional[Decimal] = Field(None, ge=0)
    late_fee_day_11: Optional[Decimal] = Field(None, ge=0)
    late_fee_day_16: Optional[Decimal] = Field(None, ge=0)
    late_fee_day_21: Optional[Decimal] = Field(None, ge=0)
    nsf_fee: Optional[Decimal] = Field(None, ge=0)
    
    # Security Deposit
    security_deposit: Optional[Decimal] = Field(None, ge=0)
    deposit_return_days: Optional[int] = Field(None, ge=1)
    
    # All other fields...
    max_occupants: Optional[int] = Field(None, ge=1)
    max_adults: Optional[int] = Field(None, ge=1)
    max_children: Optional[bool] = None
    utilities_tenant: Optional[str] = Field(None, max_length=500)
    utilities_landlord: Optional[str] = Field(None, max_length=500)
    pets_allowed: Optional[bool] = None
    pet_fee_one: Optional[Decimal] = Field(None, ge=0)
    pet_fee_two: Optional[Decimal] = Field(None, ge=0)
    max_pets: Optional[int] = Field(None, ge=0)
    parking_spaces: Optional[int] = Field(None, ge=0)
    parking_small_vehicles: Optional[int] = Field(None, ge=0)
    parking_large_trucks: Optional[int] = Field(None, ge=0)
    front_door_keys: Optional[int] = Field(None, ge=0)
    back_door_keys: Optional[int] = Field(None, ge=0)
    key_replacement_fee: Optional[Decimal] = Field(None, ge=0)
    has_shared_driveway: Optional[bool] = None
    shared_driveway_with: Optional[str] = Field(None, max_length=200)
    snow_removal_responsibility: Optional[str] = Field(None, max_length=50)
    has_garage: Optional[bool] = None
    garage_outlets_prohibited: Optional[bool] = None
    has_attic: Optional[bool] = None
    attic_usage: Optional[str] = Field(None, max_length=500)
    has_basement: Optional[bool] = None
    appliances_provided: Optional[str] = Field(None, max_length=1000)
    lead_paint_disclosure: Optional[bool] = None
    lead_paint_year_built: Optional[int] = Field(None, ge=1800, le=2100)
    early_termination_allowed: Optional[bool] = None
    early_termination_notice_days: Optional[int] = Field(None, ge=0)
    early_termination_fee_months: Optional[int] = Field(None, ge=0)
    early_termination_fee_amount: Optional[Decimal] = Field(None, ge=0)
    moveout_costs: Optional[List[MoveOutCostItem]] = None
    methamphetamine_disclosure: Optional[bool] = None
    owner_name: Optional[str] = Field(None, max_length=200)
    owner_address: Optional[str] = Field(None, max_length=500)
    manager_name: Optional[str] = Field(None, max_length=200)
    manager_address: Optional[str] = Field(None, max_length=500)
    deposit_account_info: Optional[str] = Field(None, max_length=500)
    moveout_inspection_rights: Optional[bool] = None
    military_termination_days: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class PropertySummary(BaseModel):
    """Property summary for lease response"""
    id: UUID
    display_name: str
    address: str
    city: str
    state: str
    zip_code: Optional[str] = None
    year_built: Optional[int] = None


class LeaseResponse(LeaseBase):
    """Lease response with all details"""
    id: UUID
    user_id: UUID
    lease_version: int
    property: PropertySummary
    unit: Optional[dict] = None
    tenants: List[TenantResponse]
    signed_date: Optional[date] = None
    generated_pdf_document_id: Optional[str] = None
    pdf_url: Optional[str] = None
    latex_url: Optional[str] = None
    template_used: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class LeaseListItem(BaseModel):
    """Condensed lease info for list view"""
    id: UUID
    property: PropertySummary
    tenants: List[dict]  # Just name info
    commencement_date: date
    termination_date: date
    monthly_rent: Decimal
    status: str
    pdf_url: Optional[str] = None
    created_at: datetime


class LeaseListResponse(BaseModel):
    """Paginated list of leases"""
    leases: List[LeaseListItem]
    total: int


class GeneratePDFRequest(BaseModel):
    """Request to generate PDF"""
    regenerate: bool = Field(False, description="Force regeneration even if PDF exists")


class GeneratePDFResponse(BaseModel):
    """Response from PDF generation"""
    lease_id: UUID
    pdf_url: str
    latex_url: str
    pdf_blob_name: str
    latex_blob_name: str
    generated_at: datetime
    status: str


class TerminateLeaseRequest(BaseModel):
    """Request to terminate lease early"""
    termination_date: date
    reason: str = Field(..., min_length=1, max_length=1000)
    early_termination_fee_paid: bool = False


class TerminateLeaseResponse(BaseModel):
    """Response from lease termination"""
    lease_id: UUID
    status: str
    original_termination_date: date
    actual_termination_date: date
    reason: str


