"""Pydantic schemas for document storage API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
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
    INSPECTION = "inspection"
    PHOTO = "photo"
    OTHER = "other"


class DocumentResponse(BaseModel):
    """Schema for document response"""
    id: UUID
    blob_location: str = Field(..., description="URL or path to blob storage location")
    file_name: str = Field(..., description="Original file name")
    file_type: Optional[str] = Field(None, description="MIME type or file extension")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    document_type: Optional[DocumentType] = Field(None, description="Type of document")
    property_id: Optional[UUID] = Field(None, description="Associated property ID")
    unit_id: Optional[UUID] = Field(None, description="Associated unit ID")
    tenant_id: Optional[UUID] = Field(None, description="Associated tenant ID")
    display_name: Optional[str] = Field(None, description="User-defined display name")
    document_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    uploaded_by_user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True
    
    @classmethod
    def from_document(cls, doc: Dict[str, Any]) -> "DocumentResponse":
        """Create response from document dict"""
        try:
            # Handle document_type - validate against enum, fallback to OTHER
            doc_type = doc.get("document_type")
            if doc_type:
                try:
                    doc_type = DocumentType(doc_type)
                except ValueError:
                    doc_type = DocumentType.OTHER
            
            # Handle property_id, unit_id, and tenant_id - could be None or empty string
            property_id = doc.get("property_id")
            if property_id == "" or property_id == "None" or property_id is None:
                property_id = None
                
            unit_id = doc.get("unit_id")
            if unit_id == "" or unit_id == "None" or unit_id is None:
                unit_id = None
            
            tenant_id = doc.get("tenant_id")
            if tenant_id == "" or tenant_id == "None" or tenant_id is None:
                tenant_id = None
            
            # Handle user_id field
            user_id = doc.get("uploaded_by_user_id") or doc.get("user_id")
            if user_id == "" or user_id == "None":
                user_id = None
            
            # Get display_name directly (it's now a direct column)
            display_name = doc.get("display_name")
            if display_name == "" or display_name == "None":
                display_name = None
            
            # Handle document_metadata for backwards compatibility
            metadata = doc.get("document_metadata")
            if not isinstance(metadata, dict):
                metadata = None
            
            return cls(
                id=doc["id"],
                blob_location=doc["blob_location"],
                file_name=doc["file_name"],
                file_type=doc.get("file_type"),
                file_size=doc.get("file_size"),
                document_type=doc_type,
                property_id=property_id,
                unit_id=unit_id,
                tenant_id=tenant_id,
                display_name=display_name,
                document_metadata=metadata,
                uploaded_by_user_id=user_id,
                created_at=doc["created_at"],
                updated_at=doc["updated_at"],
                expires_at=doc.get("expires_at")
            )
        except Exception as e:
            # Log the problematic document for debugging
            import logging
            logging.error(f"Error parsing document: {e}, doc keys: {doc.keys()}, doc: {doc}")
            raise


class DocumentUpdateRequest(BaseModel):
    """Schema for updating document metadata"""
    property_id: UUID = Field(..., description="Property ID (required)")
    unit_id: Optional[UUID] = Field(None, description="Associate with unit (null to remove)")
    tenant_id: Optional[UUID] = Field(None, description="Associate with tenant (null to remove)")
    document_type: Optional[DocumentType] = Field(None, description="Document type")
    display_name: Optional[str] = Field(None, max_length=255, description="Custom display name")
    clear_property: Optional[bool] = Field(False, description="If true, removes property association")


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

