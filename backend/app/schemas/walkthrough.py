"""Pydantic schemas for property walkthrough inspections"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class WalkthroughAreaPhoto(BaseModel):
    """Photo within a walkthrough area"""
    photo_blob_name: str = Field(..., description="ADLS blob name for photo")
    photo_url: Optional[str] = Field(None, description="Temporary SAS URL for viewing")
    notes: Optional[str] = Field(None, max_length=1000, description="Notes about this photo")
    order: int = Field(..., ge=1, description="Display order")


class WalkthroughAreaIssue(BaseModel):
    """Issue found in an area"""
    description: str = Field(..., min_length=1, max_length=500)
    severity: Literal["minor", "moderate", "major"] = Field(default="minor")
    estimated_cost: Optional[Decimal] = Field(None, ge=0)


class WalkthroughAreaBase(BaseModel):
    """Base walkthrough area model"""
    floor: str = Field(..., max_length=100, description="e.g., 'Basement', 'Floor 1', 'Floor 2'")
    area_name: str = Field(..., max_length=100, description="e.g., 'Living Room', 'Bathroom', 'Kitchen'")
    condition: Literal["excellent", "good", "fair", "poor"] = Field(default="good")
    notes: Optional[str] = Field(None, max_length=2000)
    issues: List[WalkthroughAreaIssue] = Field(default_factory=list)


class WalkthroughAreaCreate(WalkthroughAreaBase):
    """Area creation (no IDs needed)"""
    pass


class WalkthroughAreaResponse(WalkthroughAreaBase):
    """Area response"""
    id: UUID
    walkthrough_id: UUID
    area_order: int
    photos: List[WalkthroughAreaPhoto] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WalkthroughBase(BaseModel):
    """Base walkthrough model"""
    property_id: UUID
    unit_id: Optional[UUID] = Field(None, description="For multi-unit properties")
    walkthrough_type: Literal["move_in", "move_out", "periodic", "maintenance"] = Field(
        default="move_in",
        description="Type of walkthrough inspection"
    )
    walkthrough_date: date = Field(default_factory=date.today)
    inspector_name: Optional[str] = Field(None, max_length=200)
    tenant_name: Optional[str] = Field(None, max_length=200, description="Tenant present during inspection")
    tenant_signed: bool = Field(default=False)
    tenant_signature_date: Optional[date] = None
    landlord_signed: bool = Field(default=False)
    landlord_signature_date: Optional[date] = None
    overall_condition: Literal["excellent", "good", "fair", "poor"] = Field(default="good")
    notes: Optional[str] = Field(None, max_length=5000)


class WalkthroughCreate(WalkthroughBase):
    """Walkthrough creation with areas"""
    areas: List[WalkthroughAreaCreate] = Field(..., min_length=1, description="At least one area required")


class WalkthroughUpdate(BaseModel):
    """Walkthrough update (all fields optional)"""
    walkthrough_date: Optional[date] = None
    inspector_name: Optional[str] = Field(None, max_length=200)
    tenant_name: Optional[str] = Field(None, max_length=200)
    tenant_signed: Optional[bool] = None
    tenant_signature_date: Optional[date] = None
    landlord_signed: Optional[bool] = None
    landlord_signature_date: Optional[date] = None
    overall_condition: Optional[Literal["excellent", "good", "fair", "poor"]] = None
    notes: Optional[str] = None


class WalkthroughResponse(WalkthroughBase):
    """Walkthrough response"""
    id: UUID
    user_id: UUID
    status: Literal["draft", "pending_signature", "completed"] = Field(default="draft")
    generated_pdf_blob_name: Optional[str] = None
    pdf_url: Optional[str] = None
    areas: List[WalkthroughAreaResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WalkthroughListResponse(BaseModel):
    """Paginated walkthrough list"""
    items: List[WalkthroughResponse]
    total: int


class PhotoUploadRequest(BaseModel):
    """Request for photo upload to specific area"""
    area_id: UUID
    notes: Optional[str] = Field(None, max_length=1000)
    order: Optional[int] = Field(1, ge=1)

