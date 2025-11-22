"""Database connection and Iceberg catalog setup"""
from typing import Optional, Union
from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.catalog.hadoop import HadoopCatalog
from pyiceberg.catalog.jdbc import JdbcCatalog

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global catalog instance (can be different types)
catalog: Optional[Union[RestCatalog, HadoopCatalog, JdbcCatalog]] = None


def get_catalog() -> Union[RestCatalog, HadoopCatalog, JdbcCatalog]:
    """
    Get or create the Iceberg catalog connection.
    Supports multiple catalog types: hadoop, jdbc, rest (nessie), hive
    """
    global catalog
    
    if catalog is None:
        catalog_type = settings.ICEBERG_CATALOG_TYPE.lower()
        
        try:
            if catalog_type == "hadoop":
                # HadoopCatalog - file-based, uses Azure Blob Storage directly
                if not settings.DATABASE_URL:
                    raise ValueError("DATABASE_URL (warehouse path) required for HadoopCatalog")
                
                catalog = load_catalog(
                    "hadoop",
                    **{
                        "warehouse": settings.DATABASE_URL,
                        "type": "hadoop"
                    }
                )
                logger.info(f"Connected to HadoopCatalog with warehouse: {settings.DATABASE_URL}")
                
            elif catalog_type == "jdbc":
                # JdbcCatalog - direct JDBC connection
                if not settings.DATABASE_URL:
                    raise ValueError("DATABASE_URL (JDBC connection string) required for JdbcCatalog")
                
                catalog = load_catalog(
                    "jdbc",
                    **{
                        "uri": settings.DATABASE_URL,
                        "warehouse": settings.DATABASE_URL,
                    }
                )
                logger.info(f"Connected to JdbcCatalog: {settings.DATABASE_URL}")
                
            elif catalog_type in ["rest", "nessie"]:
                # REST Catalog (Nessie)
                if not settings.ICEBERG_CATALOG_URI:
                    raise ValueError("ICEBERG_CATALOG_URI required for REST catalog")
                
                catalog = load_catalog(
                    "nessie",
                    uri=settings.ICEBERG_CATALOG_URI,
                    **{
                        "warehouse": settings.DATABASE_URL or "",
                    }
                )
                logger.info(f"Connected to Nessie REST catalog: {settings.ICEBERG_CATALOG_URI}")
                
            elif catalog_type == "hive":
                # HiveCatalog - uses Hive Metastore
                if not settings.DATABASE_URL:
                    raise ValueError("DATABASE_URL (Hive Metastore URI) required for HiveCatalog")
                
                catalog = load_catalog(
                    "hive",
                    **{
                        "uri": settings.DATABASE_URL,
                        "warehouse": settings.DATABASE_URL,
                    }
                )
                logger.info(f"Connected to HiveCatalog: {settings.DATABASE_URL}")
                
            else:
                raise ValueError(f"Unsupported catalog type: {catalog_type}")
                
        except Exception as e:
            logger.error(f"Failed to connect to Iceberg catalog ({catalog_type}): {e}")
            raise
    
    return catalog


def close_catalog() -> None:
    """Close the catalog connection"""
    global catalog
    if catalog:
        # Nessie REST catalog doesn't require explicit closing
        catalog = None
        logger.info("Catalog connection closed")

