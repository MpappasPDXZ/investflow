"""Health check and system status endpoints"""
from fastapi import APIRouter, HTTPException
from app.core.logging import get_logger
import httpx

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("/catalog")
async def check_catalog():
    """Check catalog/database connection status"""
    try:
        from app.core.config import settings
        
        # TODO: Add your catalog/database health checks here
        return {
            "status": "ok",
            "message": "Catalog health check endpoint"
        }
    except Exception as e:
        logger.error(f"Catalog connection error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Catalog services are not accessible: {str(e)}"
        )

