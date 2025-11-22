"""Database connection and Iceberg catalog setup"""
from typing import Optional
from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.rest import RestCatalog

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global catalog instance
catalog: Optional[RestCatalog] = None


def get_catalog() -> RestCatalog:
    """
    Get or create the Iceberg catalog connection.
    Returns the Nessie REST catalog instance.
    """
    global catalog
    
    if catalog is None:
        if not settings.ICEBERG_CATALOG_URI:
            raise ValueError("ICEBERG_CATALOG_URI not configured")
        
        try:
            # Load Nessie REST catalog
            catalog = load_catalog(
                "nessie",
                uri=settings.ICEBERG_CATALOG_URI,
                **{
                    "warehouse": settings.DATABASE_URL or "",
                }
            )
            logger.info(f"Connected to Iceberg catalog: {settings.ICEBERG_CATALOG_URI}")
        except Exception as e:
            logger.error(f"Failed to connect to Iceberg catalog: {e}")
            raise
    
    return catalog


def close_catalog() -> None:
    """Close the catalog connection"""
    global catalog
    if catalog:
        # Nessie REST catalog doesn't require explicit closing
        catalog = None
        logger.info("Catalog connection closed")

