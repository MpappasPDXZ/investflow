"""Pydantic schemas for property walkthrough inspections"""
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Literal
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class WalkthroughAreaPhoto(BaseModel):
    """Photo within a walkthrough area"""
    photo_blob_name: str = Field(..., description="ADLS blob name for photo (for backward compatibility)")
    photo_url: Optional[str] = Field(None, description="Temporary SAS URL for viewing")
    notes: Optional[str] = Field(None, max_length=1000, description="Notes about this photo")
    order: int = Field(..., ge=1, description="Display order")
    document_id: Optional[str] = Field(None, description="Document ID from vault table (preferred)")


class WalkthroughAreaIssue(BaseModel):
    """Issue found in an area"""
    description: str = Field(..., min_length=1, max_length=500)
    severity: Literal["minor", "moderate", "major"] = Field(default="minor")
    estimated_cost: Optional[Decimal] = Field(None, ge=0)


class WalkthroughAreaBase(BaseModel):
    """Base walkthrough area model"""
    floor: str = Field(..., max_length=100, description="e.g., 'Basement', 'Floor 1', 'Floor 2'")
    area_name: str = Field(..., max_length=100, description="e.g., 'Living Room', 'Bathroom', 'Kitchen'")
    inspection_status: Literal["no_issues", "issue_noted_as_is", "issue_landlord_to_fix"] = Field(
        default="no_issues",
        description="Inspection status: no_issues, issue_noted_as_is, or issue_landlord_to_fix"
    )
    notes: Optional[str] = Field(None, max_length=2000, description="General notes (available for all statuses)")
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
    property_display_name: Optional[str] = Field(None, max_length=500, description="Denormalized property display name for faster queries")
    unit_number: Optional[str] = Field(None, max_length=50, description="Denormalized unit number for faster queries")
    walkthrough_type: Literal["move_in", "move_out", "periodic", "maintenance"] = Field(
        default="move_in",
        description="Type of walkthrough inspection"
    )
    walkthrough_date: date = Field(default_factory=date.today)
    inspector_name: Optional[str] = Field(None, max_length=200, description="Inspector/Landlord name")
    tenant_name: Optional[str] = Field(None, max_length=200, description="Tenant present during inspection")
    tenant_signature_date: Optional[date] = None
    landlord_signature_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=5000)


class WalkthroughCreate(WalkthroughBase):
    """Walkthrough creation with areas"""
    areas: List[WalkthroughAreaCreate] = Field(..., min_length=1, description="At least one area required")


class WalkthroughUpdate(BaseModel):
    """Walkthrough update (all fields optional)"""
    walkthrough_date: Optional[date] = None
    inspector_name: Optional[str] = Field(None, max_length=200)
    tenant_name: Optional[str] = Field(None, max_length=200)
    tenant_signature_date: Optional[date] = None
    landlord_signature_date: Optional[date] = None
    notes: Optional[str] = None


class WalkthroughResponse(WalkthroughBase):
    """Walkthrough response"""
    id: UUID
    status: Literal["draft", "pending_signature", "completed"] = Field(default="draft")
    generated_pdf_blob_name: Optional[str] = None
    pdf_url: Optional[str] = None
    areas: List[WalkthroughAreaResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WalkthroughListItem(BaseModel):
    """Simplified walkthrough for list view (no areas)"""
    id: UUID
    property_id: UUID
    unit_id: Optional[UUID] = None
    property_display_name: Optional[str] = None
    unit_number: Optional[str] = None
    walkthrough_type: Literal["move_in", "move_out", "periodic", "maintenance"]
    walkthrough_date: date
    inspector_name: Optional[str] = None
    tenant_name: Optional[str] = None
    status: Literal["draft", "pending_signature", "completed"] = Field(default="draft")
    generated_pdf_blob_name: Optional[str] = None
    pdf_url: Optional[str] = None
    areas_count: int = Field(default=0, description="Number of areas in this walkthrough")
    created_at: datetime
    updated_at: datetime


class WalkthroughListResponse(BaseModel):
    """Paginated walkthrough list"""
    items: List[WalkthroughListItem]
    total: int


class PhotoUploadRequest(BaseModel):
    """Request for photo upload to specific area"""
    area_id: UUID
    notes: Optional[str] = Field(None, max_length=1000)
    order: Optional[int] = Field(1, ge=1)

