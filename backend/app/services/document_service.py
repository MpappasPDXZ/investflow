"""Document service for managing documents in Iceberg and ADLS"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pyiceberg.expressions import EqualTo, And
from app.services.adls_service import adls_service
from app.core.iceberg import get_catalog
from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentService:
    """Service for managing document metadata in Iceberg"""
    
    def __init__(self):
        self.catalog = get_catalog()
        self.namespace = "investflow"
        self.table_name = "document_metadata"
    
    def _get_table(self):
        """Get the document metadata table"""
        return self.catalog.load_table(f"{self.namespace}.{self.table_name}")
    
    def upload_document(
        self,
        user_id: uuid.UUID,
        file_content: bytes,
        filename: str,
        content_type: str,
        document_type: str,
        property_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        document_metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload a document to ADLS and store metadata in Iceberg
        
        Args:
            user_id: User uploading the document
            file_content: File content as bytes
            filename: Original filename
            content_type: MIME type
            document_type: Type of document (receipt, lease, screening, etc.)
            property_id: Optional property ID
            unit_id: Optional unit ID
            document_metadata: Optional additional metadata
        
        Returns:
            Document metadata dictionary
        """
        try:
            # Upload to ADLS
            blob_metadata = adls_service.upload_blob(
                file_content=file_content,
                filename=filename,
                content_type=content_type,
                user_id=str(user_id),
                property_id=str(property_id) if property_id else None,
                document_type=document_type
            )
            
            # Create document record
            doc_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            record = {
                "id": doc_id,
                "user_id": str(user_id),
                "property_id": str(property_id) if property_id else None,
                "unit_id": str(unit_id) if unit_id else None,
                "blob_location": blob_metadata["blob_location"],
                "container_name": blob_metadata["container_name"],
                "blob_name": blob_metadata["blob_name"],
                "file_name": blob_metadata["file_name"],
                "file_type": blob_metadata["file_type"],
                "file_size": blob_metadata["file_size"],
                "document_type": document_type,
                "document_metadata": document_metadata or {},
                "uploaded_at": now,
                "expires_at": None,
                "is_deleted": False,
                "created_at": now,
                "updated_at": now
            }
            
            # Write to Iceberg
            table = self._get_table()
            import pyarrow as pa
            
            # Create PyArrow Table (not RecordBatch - PyIceberg requires Table)
            schema = table.schema().as_arrow()
            arrow_table = pa.Table.from_pylist([record], schema=schema)
            
            table.append(arrow_table)
            
            logger.info(f"Created document record: {doc_id}")
            
            return record
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}", exc_info=True)
            raise
    
    def get_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID (with user access check)
        
        Args:
            document_id: Document ID
            user_id: User ID for access control
        
        Returns:
            Document metadata dictionary or None if not found
        """
        try:
            table = self._get_table()
            
            # Query for the document
            scan = table.scan(
                row_filter=And(
                    EqualTo("id", str(document_id)),
                    EqualTo("user_id", str(user_id)),
                    EqualTo("is_deleted", False)
                )
            )
            
            # Get first result
            for batch in scan.to_arrow():
                if len(batch) > 0:
                    return batch.to_pylist()[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting document: {e}", exc_info=True)
            return None
    
    def get_document_download_url(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
        """
        Get a SAS URL for downloading a document
        
        Args:
            document_id: Document ID
            user_id: User ID for access control
        
        Returns:
            SAS download URL or None if not found
        """
        try:
            document = self.get_document(document_id, user_id)
            
            if not document:
                return None
            
            # Generate SAS URL
            return adls_service.get_blob_download_url(document["blob_name"])
            
        except Exception as e:
            logger.error(f"Error getting document download URL: {e}", exc_info=True)
            return None
    
    def list_documents(
        self,
        user_id: uuid.UUID,
        property_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        document_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List documents with optional filters
        
        Args:
            user_id: User ID
            property_id: Optional property filter
            unit_id: Optional unit filter
            document_type: Optional document type filter
            skip: Number of records to skip
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (list of documents, total count)
        """
        try:
            table = self._get_table()
            
            # Build filter
            filters = [
                EqualTo("user_id", str(user_id)),
                EqualTo("is_deleted", False)
            ]
            
            if property_id:
                filters.append(EqualTo("property_id", str(property_id)))
            
            if unit_id:
                filters.append(EqualTo("unit_id", str(unit_id)))
            
            if document_type:
                filters.append(EqualTo("document_type", document_type))
            
            # Combine filters
            row_filter = filters[0]
            for f in filters[1:]:
                row_filter = And(row_filter, f)
            
            # Query
            scan = table.scan(row_filter=row_filter)
            
            # Collect all results - scan.to_arrow() returns a Table
            arrow_table = scan.to_arrow()
            all_docs = arrow_table.to_pylist()
            
            # Sort by uploaded_at descending
            all_docs.sort(key=lambda x: x["uploaded_at"], reverse=True)
            
            total = len(all_docs)
            paginated_docs = all_docs[skip:skip + limit]
            
            return paginated_docs, total
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}", exc_info=True)
            return [], 0
    
    def soft_delete_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """
        Soft delete a document (mark as deleted in Iceberg, keep in ADLS)
        
        Args:
            document_id: Document ID
            user_id: User ID for access control
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the document
            document = self.get_document(document_id, user_id)
            
            if not document:
                return False
            
            # Update the record to mark as deleted
            # Note: Iceberg doesn't support in-place updates, so we need to:
            # 1. Delete the old record (row-level delete)
            # 2. Insert a new record with is_deleted=True
            
            table = self._get_table()
            
            # Delete old record
            table.delete(
                And(
                    EqualTo("id", str(document_id)),
                    EqualTo("user_id", str(user_id))
                )
            )
            
            # Insert updated record
            document["is_deleted"] = True
            document["updated_at"] = datetime.utcnow()
            
            import pyarrow as pa
            schema = table.schema().as_arrow()
            arrow_table = pa.Table.from_pylist([document], schema=schema)
            table.append(arrow_table)
            
            logger.info(f"Soft deleted document: {document_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error soft deleting document: {e}", exc_info=True)
            return False


# Global instance
document_service = DocumentService()


# Convenience functions for use in API routes
def upload_document(
    user_id: uuid.UUID,
    file_content: bytes,
    filename: str,
    content_type: str,
    document_type: str,
    property_id: Optional[uuid.UUID] = None,
    unit_id: Optional[uuid.UUID] = None,
    document_metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Upload a document"""
    return document_service.upload_document(
        user_id=user_id,
        file_content=file_content,
        filename=filename,
        content_type=content_type,
        document_type=document_type,
        property_id=property_id,
        unit_id=unit_id,
        document_metadata=document_metadata
    )


def get_document(document_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Get a document by ID"""
    return document_service.get_document(document_id, user_id)


def get_document_download_url(document_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
    """Get download URL for a document"""
    return document_service.get_document_download_url(document_id, user_id)


def list_documents(
    user_id: uuid.UUID,
    property_id: Optional[uuid.UUID] = None,
    unit_id: Optional[uuid.UUID] = None,
    document_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Dict[str, Any]], int]:
    """List documents with filters"""
    return document_service.list_documents(
        user_id=user_id,
        property_id=property_id,
        unit_id=unit_id,
        document_type=document_type,
        skip=skip,
        limit=limit
    )


def delete_document(document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Soft delete a document"""
    return document_service.soft_delete_document(document_id, user_id)
