"""Azure Data Lake Storage (ADLS) service for document management"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ADLSService:
    """Service for interacting with Azure Data Lake Storage"""
    
    def __init__(self):
        # Use connection string if provided, otherwise build from account name/key
        if settings.AZURE_STORAGE_CONNECTION_STRING:
            connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
            # Extract account name and key from connection string
            parts = dict(part.split("=", 1) for part in connection_string.split(";") if "=" in part)
            self.account_name = parts.get("AccountName", "")
            self.account_key = parts.get("AccountKey", "")
        elif settings.AZURE_STORAGE_ACCOUNT_NAME and settings.AZURE_STORAGE_ACCOUNT_KEY:
            connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={settings.AZURE_STORAGE_ACCOUNT_NAME};"
                f"AccountKey={settings.AZURE_STORAGE_ACCOUNT_KEY};"
                f"EndpointSuffix=core.windows.net"
            )
            self.account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
            self.account_key = settings.AZURE_STORAGE_ACCOUNT_KEY
        else:
            raise ValueError("Azure Storage credentials not configured. Set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY")
        
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = settings.AZURE_STORAGE_CONTAINER_NAME
        
        # Ensure container exists
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {self.container_name}")
        except Exception as e:
            logger.error(f"Error ensuring container exists: {e}")
    
    def upload_blob(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        user_id: str,
        property_id: Optional[str] = None,
        document_type: str = "other"
    ) -> dict:
        """
        Upload a file to ADLS and return metadata
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            content_type: MIME type
            user_id: User uploading the document
            property_id: Optional property ID
            document_type: Type of document (receipt, lease, screening, etc.)
        
        Returns:
            Dictionary with blob metadata including blob_name, blob_location, etc.
        """
        try:
            # Generate unique blob name
            file_ext = filename.split('.')[-1] if '.' in filename else ''
            blob_id = str(uuid.uuid4())
            
            # Organize into folders: expenses for receipts, user_documents for others
            if document_type == "receipt":
                folder = "expenses"
            else:
                folder = "user_documents"
            
            # Structure: folder/user_id/blob_id.ext
            blob_name = f"{folder}/{user_id}/{blob_id}.{file_ext}"
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Upload blob
            blob_client.upload_blob(
                file_content,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
                metadata={
                    "user_id": user_id,
                    "property_id": property_id or "",
                    "document_type": document_type,
                    "original_filename": filename,
                    "uploaded_at": datetime.utcnow().isoformat()
                }
            )
            
            # Get blob URL
            blob_url = blob_client.url
            
            logger.info(f"Uploaded blob: {blob_name} ({len(file_content)} bytes)")
            
            return {
                "blob_name": blob_name,
                "blob_location": blob_url,
                "container_name": self.container_name,
                "file_name": filename,
                "file_type": content_type,
                "file_size": len(file_content)
            }
            
        except Exception as e:
            logger.error(f"Error uploading blob: {e}", exc_info=True)
            raise
    
    def get_blob_download_url(self, blob_name: str, expiry_hours: int = 24) -> str:
        """
        Generate a SAS URL for downloading a blob
        
        Args:
            blob_name: Name of the blob
            expiry_hours: Hours until the SAS token expires (default 24 hours)
        
        Returns:
            SAS URL for downloading the blob
        """
        try:
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            # Construct blob URL with SAS token
            blob_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"
            
            return blob_url
            
        except Exception as e:
            logger.error(f"Error generating download URL: {e}", exc_info=True)
            raise
    
    def download_blob(self, blob_name: str) -> tuple[bytes, str, str]:
        """
        Download blob content
        
        Args:
            blob_name: Name of the blob to download
        
        Returns:
            Tuple of (blob_content, content_type, filename)
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Download blob
            download_stream = blob_client.download_blob()
            blob_content = download_stream.readall()
            
            # Get metadata
            properties = blob_client.get_blob_properties()
            content_type = properties.content_settings.content_type or "application/octet-stream"
            
            # Extract filename from blob_name (last part after /)
            filename = blob_name.split('/')[-1]
            
            return blob_content, content_type, filename
            
        except Exception as e:
            logger.error(f"Error downloading blob: {e}", exc_info=True)
            raise
    
    def delete_blob(self, blob_name: str) -> bool:
        """
        Delete a blob from ADLS
        
        Args:
            blob_name: Name of the blob to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            blob_client.delete_blob()
            logger.info(f"Deleted blob: {blob_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting blob: {e}", exc_info=True)
            return False
    
    def blob_exists(self, blob_name: str) -> bool:
        """Check if a blob exists"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            return blob_client.exists()
        except Exception as e:
            logger.error(f"Error checking blob existence: {e}", exc_info=True)
            return False


# Global instance
adls_service = ADLSService()

