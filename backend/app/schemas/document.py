"""Pydantic schemas for document storage API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum


class DocumentType(str, Enum):
    """Document type enum"""
    RECEIPT = "receipt"
    LEASE = "lease"
    BACKGROUND_CHECK = "background_check"
    CONTRACT = "contract"
    INVOICE = "invoice"
    OTHER = "other"


class DocumentResponse(BaseModel):
    """Schema for document response"""
    id: UUID
    blob_location: str = Field(..., description="URL or path to blob storage location")
    file_name: str = Field(..., description="Original file name")
    file_type: Optional[str] = Field(None, description="MIME type or file extension")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    document_type: Optional[DocumentType] = Field(None, description="Type of document")
    metadata: Optional[str] = Field(None, description="Additional metadata (JSON string)")
    uploaded_by_user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response"""
    document: DocumentResponse
    download_url: str = Field(..., description="Temporary download URL (expires in 1 hour)")


class DocumentListResponse(BaseModel):
    """Schema for paginated document list response"""
    items: list[DocumentResponse]
    total: int
    page: int
    limit: int

