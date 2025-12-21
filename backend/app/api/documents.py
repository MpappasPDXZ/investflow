"""API routes for document management"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from uuid import UUID
import io

from app.core.dependencies import get_current_user
from app.schemas.document import DocumentResponse, DocumentUploadResponse, DocumentListResponse, DocumentUpdateRequest
from app.services import document_service
from app.services.adls_service import adls_service
from app.core.logging import get_logger

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document_endpoint(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form("other"),
    property_id: Optional[str] = Form(None),
    unit_id: Optional[str] = Form(None),
    tenant_id: Optional[str] = Form(None),
    display_name: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """Upload a document to Azure Blob Storage"""
    try:
        # Validate file type
        allowed_types = [
            "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
            "application/pdf",
            "image/heic", "image/heif"  # iOS photo formats
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
        
        # Build metadata with display_name if provided
        # Upload document with display_name passed directly
        document = document_service.upload_document(
            user_id=user_id,
            file_content=file_content,
            filename=file.filename or "document",
            content_type=content_type,
            document_type=document_type or "other",
            property_id=UUID(property_id) if property_id else None,
            unit_id=UUID(unit_id) if unit_id else None,
            tenant_id=UUID(tenant_id) if tenant_id else None,
            display_name=display_name.strip() if display_name else None
        )
        
        # Generate download URL
        download_url = document_service.get_document_download_url(UUID(document["id"]), user_id)
        
        return DocumentUploadResponse(
            document=DocumentResponse.from_document(document),
            download_url=download_url or document["blob_location"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=DocumentListResponse)
async def list_documents_endpoint(
    property_id: Optional[UUID] = Query(None, description="Filter by property ID"),
    unit_id: Optional[UUID] = Query(None, description="Filter by unit ID"),
    tenant_id: Optional[UUID] = Query(None, description="Filter by tenant ID"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """List documents for the current user"""
    try:
        user_id = UUID(current_user["sub"])
        logger.info(f"Listing documents for user {user_id}")
        
        documents, total = document_service.list_documents(
            user_id=user_id,
            property_id=property_id,
            unit_id=unit_id,
            tenant_id=tenant_id,
            document_type=document_type,
            skip=skip,
            limit=limit
        )
        
        logger.info(f"Found {len(documents)} documents, parsing...")
        
        items = []
        for i, doc in enumerate(documents):
            try:
                items.append(DocumentResponse.from_document(doc))
            except Exception as parse_err:
                logger.error(f"Error parsing document {i}: {parse_err}, doc: {doc}")
                # Skip problematic documents instead of failing entirely
                continue
        
        logger.info(f"Successfully parsed {len(items)} documents")
        
        return DocumentListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_endpoint(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get document metadata by ID"""
    try:
        user_id = UUID(current_user["sub"])
        document = document_service.get_document(document_id, user_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return DocumentResponse.from_document(document)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document_endpoint(
    document_id: UUID,
    update_data: DocumentUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update document metadata (property assignment, name, type)"""
    try:
        user_id = UUID(current_user["sub"])
        
        logger.info(f"Updating document {document_id} with data: {update_data}")
        
        updated_document = document_service.update_document(
            document_id=document_id,
            user_id=user_id,
            property_id=update_data.property_id,
            unit_id=update_data.unit_id,
            document_type=update_data.document_type.value if update_data.document_type else None,
            display_name=update_data.display_name,
            clear_property=update_data.clear_property or False
        )
        
        if not updated_document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        logger.info(f"Document updated successfully, building response")
        
        response = DocumentResponse.from_document(updated_document)
        logger.info(f"Response built: {response.id}")
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/download")
async def download_document_endpoint(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get download URL for a document"""
    try:
        user_id = UUID(current_user["sub"])
        download_url = document_service.get_document_download_url(document_id, user_id)
        
        if not download_url:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"download_url": download_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document download URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/proxy")
async def proxy_document_download(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Proxy download for a document (forces actual download instead of opening in browser)"""
    try:
        user_id = UUID(current_user["sub"])
        
        # Get document metadata
        document = document_service.get_document(document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Download blob content
        blob_content, content_type, filename = adls_service.download_blob(document["blob_name"])
        
        # Use display_name if available, otherwise use original filename
        download_filename = document.get("display_name") or document.get("file_name") or filename
        
        # Return as streaming response with Content-Disposition header to force download
        return StreamingResponse(
            io.BytesIO(blob_content),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{download_filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying document download: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}", status_code=204)
async def delete_document_endpoint(
    document_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Soft delete a document"""
    try:
        user_id = UUID(current_user["sub"])
        success = document_service.delete_document(document_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

