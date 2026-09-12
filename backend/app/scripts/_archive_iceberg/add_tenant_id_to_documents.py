#!/usr/bin/env python3
"""Add tenant_id support to document_metadata table"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog
from app.core.logging import setup_logging, get_logger
from pyiceberg.types import StringType

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)

def add_tenant_id_to_documents():
    """Add tenant_id field to document_metadata table"""
    logger.info("🔄 Adding tenant_id to document_metadata table...")
    
    try:
        catalog = get_catalog()
        table = catalog.load_table((*NAMESPACE, "document_metadata"))
        
        # Check existing schema
        existing_fields = {field.name for field in table.schema().fields}
        
        if "tenant_id" not in existing_fields:
            with table.update_schema() as update:
                update.add_column("tenant_id", StringType(), required=False)
                logger.info("  ➕ Added tenant_id")
        else:
            logger.info("  ⏭️  tenant_id already exists")
        
        logger.info("✅ Document metadata table updated successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    add_tenant_id_to_documents()

