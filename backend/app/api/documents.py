"""API routes for document management"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from uuid import UUID

from app.core.dependencies import get_current_user
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.document_service import upload_document, get_document_download_url, get_document
from app.core.logging import get_logger

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document_endpoint(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form("receipt"),
    current_user: dict = Depends(get_current_user)
):
    """Upload a document to Azure Blob Storage"""
    try:
        # Validate file type
        allowed_types = [
            "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
            "application/pdf"
        ]
        
        content_type = file.content_type or "application/octet-stream"
        if content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"File type {content_type} not allowed. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Validate file size (max 10MB)
        file_content = await file.read()
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_content) > max_size:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        user_id = UUID(current_user["sub"])
        
        # Upload document
        document = upload_document(
            user_id=user_id,
            file_content=file_content,
            filename=file.filename or "document",
            content_type=content_type,
            document_type=document_type or "receipt"
        )
        
        # Generate download URL
        download_url = get_document_download_url(document["id"], user_id)
        
        return DocumentUploadResponse(
            document=DocumentResponse(**document),
            download_url=download_url or document["blob_location"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_endpoint(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get document metadata by ID"""
    try:
        user_id = UUID(current_user["sub"])
        document = get_document(document_id, user_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return DocumentResponse(**document)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/download")
async def download_document_endpoint(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get download URL for a document"""
    try:
        user_id = UUID(current_user["sub"])
        download_url = get_document_download_url(document_id, user_id)
        
        if not download_url:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"download_url": download_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document download URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

