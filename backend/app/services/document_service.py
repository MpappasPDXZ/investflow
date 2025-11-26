"""Service layer for document storage operations using PyIceberg and Azure Blob Storage"""
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import pandas as pd
import uuid
import os
from pathlib import Path

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import AzureError

from app.services.pyiceberg_service import get_pyiceberg_service
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)
TABLE_NAME = "document_storage"


def _get_blob_service_client() -> BlobServiceClient:
    """Get Azure Blob Service Client"""
    account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
    account_key = settings.AZURE_STORAGE_ACCOUNT_KEY
    
    if not account_key:
        raise ValueError("AZURE_STORAGE_ACCOUNT_KEY not configured")
    
    connection_string = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )
    
    return BlobServiceClient.from_connection_string(connection_string)


def _generate_blob_path(user_id: UUID, document_type: str, filename: str) -> str:
    """Generate blob storage path: {user_id}/{document_type}/{year}/{month}/{filename}"""
    now = datetime.utcnow()
    year = now.year
    month = now.month
    
    # Sanitize filename
    safe_filename = "".join(c for c in filename if c.isalnum() or c in ".-_")[:255]
    
    return f"{user_id}/{document_type}/{year}/{month:02d}/{safe_filename}"


def upload_document(
    user_id: UUID,
    file_content: bytes,
    filename: str,
    content_type: str,
    document_type: Optional[str] = "receipt"
) -> Dict[str, Any]:
    """Upload a document to Azure Blob Storage and create document_storage record"""
    pyiceberg = get_pyiceberg_service()
    blob_service = _get_blob_service_client()
    
    # Generate blob path
    blob_path = _generate_blob_path(user_id, document_type or "other", filename)
    container_name = settings.AZURE_STORAGE_CONTAINER_NAME
    
    try:
        # Upload to blob storage
        blob_client = blob_service.get_blob_client(container=container_name, blob=blob_path)
        blob_client.upload_blob(file_content, overwrite=True, content_settings={"content_type": content_type})
        
        # Generate blob URL
        blob_url = f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{container_name}/{blob_path}"
        
        # Create document_storage record
        now = pd.Timestamp.now()
        document_id = str(uuid.uuid4())
        
        document_dict = {
            "id": document_id,
            "blob_location": blob_url,
            "file_name": filename,
            "file_type": content_type,
            "file_size": len(file_content),
            "document_type": document_type or "other",
            "metadata": None,
            "uploaded_by_user_id": str(user_id),
            "created_at": now,
            "updated_at": now,
            "expires_at": None,
        }
        
        # Append to table
        df = pd.DataFrame([document_dict])
        pyiceberg.append_data(NAMESPACE, TABLE_NAME, df)
        
        logger.info(f"Uploaded document {document_id} for user {user_id}: {blob_path}")
        
        # Return document info
        return {
            "id": UUID(document_id),
            "blob_location": blob_url,
            "file_name": filename,
            "file_type": content_type,
            "file_size": len(file_content),
            "document_type": document_type,
            "metadata": None,
            "uploaded_by_user_id": user_id,
            "created_at": now.to_pydatetime(),
            "updated_at": now.to_pydatetime(),
            "expires_at": None,
        }
        
    except AzureError as e:
        logger.error(f"Failed to upload document to Azure Blob Storage: {e}")
        raise


def get_document_download_url(
    document_id: UUID,
    user_id: UUID,
    expires_in_hours: int = 1
) -> Optional[str]:
    """Generate a signed download URL for a document"""
    pyiceberg = get_pyiceberg_service()
    
    # Read document from table
    df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    filtered = df[(df["id"] == str(document_id)) & (df["uploaded_by_user_id"] == str(user_id))]
    
    if len(filtered) == 0:
        return None
    
    document = filtered.iloc[0]
    blob_location = document["blob_location"]
    
    # Parse blob path from URL
    # Format: https://{account}.blob.core.windows.net/{container}/{path}
    try:
        parts = blob_location.replace(f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/", "").split("/", 1)
        container_name = parts[0]
        blob_name = parts[1] if len(parts) > 1 else ""
        
        # Generate SAS token
        blob_service = _get_blob_service_client()
        sas_token = generate_blob_sas(
            account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
            container_name=container_name,
            blob_name=blob_name,
            account_key=settings.AZURE_STORAGE_ACCOUNT_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=expires_in_hours)
        )
        
        return f"{blob_location}?{sas_token}"
        
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        return None


def get_document(
    document_id: UUID,
    user_id: UUID
) -> Optional[Dict[str, Any]]:
    """Get document metadata by ID"""
    pyiceberg = get_pyiceberg_service()
    
    # Read table and filter
    df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    filtered = df[(df["id"] == str(document_id)) & (df["uploaded_by_user_id"] == str(user_id))]
    
    if len(filtered) == 0:
        return None
    
    doc = filtered.iloc[0]
    
    return {
        "id": UUID(doc["id"]),
        "blob_location": str(doc["blob_location"]),
        "file_name": str(doc["file_name"]),
        "file_type": str(doc["file_type"]) if pd.notna(doc["file_type"]) else None,
        "file_size": int(doc["file_size"]) if pd.notna(doc["file_size"]) else None,
        "document_type": str(doc["document_type"]) if pd.notna(doc["document_type"]) else None,
        "metadata": str(doc["metadata"]) if pd.notna(doc["metadata"]) else None,
        "uploaded_by_user_id": UUID(doc["uploaded_by_user_id"]) if pd.notna(doc["uploaded_by_user_id"]) else None,
        "created_at": doc["created_at"].to_pydatetime() if pd.notna(doc["created_at"]) else None,
        "updated_at": doc["updated_at"].to_pydatetime() if pd.notna(doc["updated_at"]) else None,
        "expires_at": doc["expires_at"].to_pydatetime() if pd.notna(doc["expires_at"]) else None,
    }

