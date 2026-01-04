"""Document service for managing documents in Iceberg and ADLS"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from io import BytesIO
from pyiceberg.expressions import EqualTo, And
from app.services.adls_service import adls_service
from app.core.iceberg import get_catalog
from app.core.logging import get_logger

logger = get_logger(__name__)

def _fix_image_orientation(file_content: bytes, content_type: str) -> bytes:
    """
    Fix image orientation based on EXIF data.
    Rotates/flips the image data itself so browsers display it correctly.
    
    Args:
        file_content: Original image bytes
        content_type: MIME type of the image
        
    Returns:
        Corrected image bytes (or original if not an image or no EXIF data)
    """
    # Only process JPEG images (most common with EXIF orientation issues)
    if not content_type.startswith('image/jpeg') and not content_type.startswith('image/jpg'):
        return file_content
    
    try:
        from PIL import Image
        from PIL import ImageOps
        
        # Open image from bytes
        img = Image.open(BytesIO(file_content))
        
        # Use ImageOps.exif_transpose() to automatically correct orientation
        # This handles all EXIF orientation cases (1-8) correctly
        # If no EXIF orientation data exists, it returns the image unchanged
        corrected_img = ImageOps.exif_transpose(img)
        
        # Save corrected image to bytes, removing EXIF orientation to prevent double-rotation
        # This ensures the image displays correctly in browsers without relying on EXIF
        output = BytesIO()
        corrected_img.save(output, format='JPEG', quality=95, exif=b'')
        return output.getvalue()
        
    except ImportError:
        # Pillow not installed, return original
        logger.warning("Pillow not installed, cannot fix image orientation")
        return file_content
    except Exception as e:
        # If anything goes wrong, return original image
        logger.warning(f"Error fixing image orientation: {e}")
        return file_content


class DocumentService:
    """Service for managing document metadata in Iceberg"""
    
    def __init__(self):
        self.catalog = get_catalog()
        self.namespace = "investflow"
        self.table_name = "vault"
        self._table_cache = None
        self._table_cache_time = None
        self._cache_ttl = 60  # Cache table reference for 60 seconds
    
    def _get_table(self):
        """Get the document metadata table with caching"""
        import time
        now = time.time()
        
        # Return cached table if still valid
        if self._table_cache is not None and self._table_cache_time is not None:
            if now - self._table_cache_time < self._cache_ttl:
                return self._table_cache
        
        # Load table and cache it
        self._table_cache = self.catalog.load_table(f"{self.namespace}.{self.table_name}")
        self._table_cache_time = now
        return self._table_cache
    
    def upload_document(
        self,
        user_id: uuid.UUID,
        file_content: bytes,
        filename: str,
        content_type: str,
        document_type: str,
        property_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        tenant_id: Optional[uuid.UUID] = None,
        document_metadata: Optional[Dict[str, str]] = None,
        display_name: Optional[str] = None
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
            tenant_id: Optional tenant ID
            document_metadata: Optional additional metadata
        
        Returns:
            Document metadata dictionary
        """
        try:
            # Fix image orientation for JPEG images (fixes portrait photos rotated 90 degrees)
            processed_content = _fix_image_orientation(file_content, content_type)
            
            # Upload to ADLS
            blob_metadata = adls_service.upload_blob(
                file_content=processed_content,
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
                "tenant_id": str(tenant_id) if tenant_id else None,
                "blob_location": blob_metadata["blob_location"],
                "container_name": blob_metadata["container_name"],
                "blob_name": blob_metadata["blob_name"],
                "file_name": blob_metadata["file_name"],
                "file_type": blob_metadata["file_type"],
                "file_size": blob_metadata["file_size"],
                "document_type": document_type,
                "document_metadata": None,  # Table schema expects list<list<string>>, pass None for now
                "display_name": display_name,  # Direct column, not nested in metadata
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
            
            # Query for the document - vault table uses user_id column
            scan = table.scan(
                row_filter=And(
                    EqualTo("id", str(document_id)),
                    EqualTo("user_id", str(user_id))
                )
            )
            
            # Get first result - scan.to_arrow() returns a Table
            arrow_table = scan.to_arrow()
            if len(arrow_table) > 0:
                return arrow_table.to_pylist()[0]
            
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
        tenant_id: Optional[uuid.UUID] = None,
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
            
            # Build filter - vault table uses user_id and has property_id, unit_id, tenant_id
            filters = [
                EqualTo("user_id", str(user_id)),
                EqualTo("is_deleted", False)  # Filter out deleted documents
            ]
            
            if property_id:
                filters.append(EqualTo("property_id", str(property_id)))
            
            if unit_id:
                filters.append(EqualTo("unit_id", str(unit_id)))
            
            if tenant_id:
                filters.append(EqualTo("tenant_id", str(tenant_id)))
            
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
    
    def update_document(
        self,
        document_id: uuid.UUID,
        property_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        tenant_id: Optional[uuid.UUID] = None,
        document_type: Optional[str] = None,
        display_name: Optional[str] = None,
        clear_property: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Update a document's metadata using efficient upsert
        
        Args:
            document_id: Document ID (primary key)
            property_id: Property ID (required)
            user_id: User ID for access control (optional)
            unit_id: New unit ID (or None to keep unchanged)
            tenant_id: New tenant ID (or None to keep unchanged)
            document_type: New document type (or None to keep unchanged)
            display_name: Custom display name (or None to keep unchanged)
            clear_property: If True, remove property association (ignored if property_id is provided)
        
        Returns:
            Updated document or None if not found
        """
        try:
            # Step 1: Get existing document by primary key (id)
            table = self._get_table()
            scan = table.scan(row_filter=EqualTo("id", str(document_id)))
            arrow_table = scan.to_arrow()
            
            if len(arrow_table) == 0:
                logger.warning(f"Document {document_id} not found")
                return None
            
            document = arrow_table.to_pylist()[0]
            
            # Get user_id from document if not provided
            if not user_id:
                user_id = uuid.UUID(document.get("user_id"))
            
            # Step 2: Merge frontend changes into existing document
            # Start with existing document, then apply changes
            updated_document = document.copy()
            
            # Apply changes from frontend
            if clear_property:
                updated_document["property_id"] = None
            else:
                updated_document["property_id"] = str(property_id)
            
            if unit_id is not None:
                updated_document["unit_id"] = str(unit_id) if unit_id else None
            
            if tenant_id is not None:
                updated_document["tenant_id"] = str(tenant_id) if tenant_id else None
            
            if document_type is not None:
                updated_document["document_type"] = document_type
            
            if display_name is not None:
                updated_document["display_name"] = display_name
            
            # Update timestamp
            updated_document["updated_at"] = datetime.utcnow()
            
            # Ensure id and user_id are strings
            updated_document["id"] = str(document_id)
            updated_document["user_id"] = str(user_id)
            
            # Step 3: Fast update using delete-then-append (vault-specific, avoids duplicate row issues)
            import pandas as pd
            from app.core.iceberg import append_data
            # EqualTo is already imported at the top of the file
            
            # Get table schema to ensure correct field order
            table_schema = table.schema().as_arrow()
            schema_field_names = [field.name for field in table_schema]
            
            # Build ordered dict in exact schema order
            ordered_dict = {}
            for field_name in schema_field_names:
                value = updated_document.get(field_name)
                # Convert UUID fields to strings
                if field_name in ["id", "user_id", "property_id", "unit_id", "tenant_id"]:
                    ordered_dict[field_name] = str(value) if value else None
                else:
                    ordered_dict[field_name] = value
            
            df = pd.DataFrame([ordered_dict])
            
            # Delete existing row(s) with this ID (handles duplicates)
            table.delete(EqualTo("id", str(document_id)))
            logger.info(f"[VAULT] Deleted existing row(s) for document {document_id}, appending updated row")
            
            # Append the updated row (fast, avoids upsert complexity)
            append_data(
                namespace=(self.namespace,),
                table_name=self.table_name,
                data=df
            )
            
            logger.info(f"Updated document: {document_id}")
            
            # Return updated document
            return updated_document
            
        except Exception as e:
            logger.error(f"Error updating document: {e}", exc_info=True)
            return None

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
    tenant_id: Optional[uuid.UUID] = None,
    document_metadata: Optional[Dict[str, str]] = None,
    display_name: Optional[str] = None
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
        tenant_id=tenant_id,
        document_metadata=document_metadata,
        display_name=display_name
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
    tenant_id: Optional[uuid.UUID] = None,
    document_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Dict[str, Any]], int]:
    """List documents with filters"""
    return document_service.list_documents(
        user_id=user_id,
        property_id=property_id,
        unit_id=unit_id,
        tenant_id=tenant_id,
        document_type=document_type,
        skip=skip,
        limit=limit
    )


def delete_document(document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Soft delete a document"""
    return document_service.soft_delete_document(document_id, user_id)


def update_document(
    document_id: uuid.UUID,
    property_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    unit_id: Optional[uuid.UUID] = None,
    tenant_id: Optional[uuid.UUID] = None,
    document_type: Optional[str] = None,
    display_name: Optional[str] = None,
    clear_property: bool = False
) -> Optional[Dict[str, Any]]:
    """Update a document's metadata"""
    return document_service.update_document(
        document_id=document_id,
        property_id=property_id,
        user_id=user_id,
        unit_id=unit_id,
        tenant_id=tenant_id,
        document_type=document_type,
        display_name=display_name,
        clear_property=clear_property
    )
