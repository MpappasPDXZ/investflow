"""Health check and system status endpoints"""
from fastapi import APIRouter, HTTPException
from app.core.logging import get_logger
from app.services.auth_cache_service import auth_cache

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "message": "Service is running"
    }


@router.post("/cache/sync")
async def sync_cache():
    """
    Force sync the CDC auth cache from Iceberg source tables.
    Use this after manual database changes or to recover from cache inconsistencies.
    """
    try:
        logger.info("Manual cache sync requested")
        
        # Invalidate current cache
        auth_cache.invalidate()
        
        # Sync from Iceberg
        success = auth_cache.sync_from_iceberg()
        
        if success:
            stats = auth_cache.get_stats()
            logger.info(f"Cache synced successfully: {stats}")
            return {
                "status": "ok",
                "message": "Cache synced successfully",
                "cache": stats
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to sync cache from Iceberg"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing cache: {str(e)}"
        )
