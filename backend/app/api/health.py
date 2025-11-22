"""Health check and system status endpoints"""
from fastapi import APIRouter, HTTPException
from app.core.database import get_catalog
from app.core.logging import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("/nessie")
async def check_nessie():
    """Check Nessie catalog connection"""
    try:
        catalog = get_catalog()
        # Try to list namespaces as a basic connectivity test
        namespaces = catalog.list_namespaces()
        return {
            "status": "connected",
            "catalog_type": type(catalog).__name__,
            "namespaces_count": len(list(namespaces)),
            "message": "Nessie catalog is accessible"
        }
    except Exception as e:
        logger.error(f"Nessie connection error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Nessie catalog is not accessible: {str(e)}"
        )

