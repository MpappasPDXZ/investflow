"""
Pydantic schemas for rental comparables
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from decimal import Decimal
from datetime import datetime, date


class ComparableBase(BaseModel):
    """Base schema for rental comparables"""
    property_id: str
    unit_id: Optional[str] = None
    
    # Address
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    
    # Property classification (NEW)
    property_type: Optional[str] = None  # House, Duplex, Townhouse, Condo, Apartment
    is_furnished: Optional[bool] = None
    
    # Property details
    bedrooms: int
    bathrooms: Decimal
    square_feet: int
    asking_price: Decimal  # Monthly rental asking price
    
    # Amenities (all optional booleans)
    has_fence: Optional[bool] = None
    has_solid_flooring: Optional[bool] = None  # LVP/Hardwood
    has_quartz_granite: Optional[bool] = None  # Quartz/Granite counters
    has_ss_appliances: Optional[bool] = None   # Stainless steel appliances
    has_shaker_cabinets: Optional[bool] = None # White shaker cabinets
    has_washer_dryer: Optional[bool] = None    # W/D included
    garage_spaces: Optional[int] = None
    
    # Zillow data
    date_listed: date
    contacts: Optional[int] = None  # Zillow inquiries/contacts
    
    # Rental status (NEW)
    is_rented: Optional[bool] = None  # Has it been rented?
    
    # Historical rent data
    last_rented_price: Optional[Decimal] = None  # Actual rent achieved
    last_rented_year: Optional[int] = None
    
    # Flags
    is_subject_property: bool = False  # True if this is YOUR property
    
    notes: Optional[str] = None


class ComparableCreate(ComparableBase):
    """Schema for creating a comparable"""
    pass


class ComparableUpdate(BaseModel):
    """Schema for updating a comparable - all fields optional"""
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    
    property_type: Optional[str] = None
    is_furnished: Optional[bool] = None
    
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    square_feet: Optional[int] = None
    asking_price: Optional[Decimal] = None
    
    has_fence: Optional[bool] = None
    has_solid_flooring: Optional[bool] = None
    has_quartz_granite: Optional[bool] = None
    has_ss_appliances: Optional[bool] = None
    has_shaker_cabinets: Optional[bool] = None
    has_washer_dryer: Optional[bool] = None
    garage_spaces: Optional[int] = None
    
    date_listed: Optional[date] = None
    contacts: Optional[int] = None
    
    is_rented: Optional[bool] = None
    
    last_rented_price: Optional[Decimal] = None
    last_rented_year: Optional[int] = None
    
    is_subject_property: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class ComparableResponse(ComparableBase):
    """Schema for comparable response with calculated fields"""
    model_config = ConfigDict(json_encoders={Decimal: float})
    
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Calculated fields
    days_on_zillow: Optional[int] = None
    price_per_sf: Optional[float] = None
    contact_rate: Optional[float] = None        # CR = contacts / days_on_zillow
    actual_price_per_sf: Optional[float] = None # ACT $-SF = last_rented_price / square_feet
    adjusted_price_per_sf: Optional[float] = None  # $/SF adjusted by amenity coefficients (future)


class ComparableListResponse(BaseModel):
    """Schema for list of comparables"""
    items: list[ComparableResponse]
    total: int


# Amenity coefficients for adjusted $/SF calculation (future use)
class AmenityCoefficients(BaseModel):
    """Coefficients for adjusting $/SF based on amenities - computed from regression"""
    base_multiplier: float = 1.0
    fence_coef: float = 0.0
    flooring_coef: float = 0.0
    counters_coef: float = 0.0
    appliances_coef: float = 0.0
    cabinets_coef: float = 0.0
    washer_dryer_coef: float = 0.0
    garage_coef: float = 0.0  # Per garage space
    furnished_coef: float = 0.0
