"""Health check and system status endpoints"""
from fastapi import APIRouter, HTTPException
from app.core.logging import get_logger
from app.services.auth_cache_service import auth_cache
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


@router.get("/cache")
async def get_cache_stats():
    """Get CDC auth cache statistics"""
    try:
        stats = auth_cache.get_stats()
        return {
            "status": "ok",
            "cache": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache stats: {str(e)}"
        )


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


@router.post("/cache/invalidate")
async def invalidate_cache():
    """
    Invalidate the CDC auth cache.
    Cache will be rebuilt on next access.
    """
    try:
        auth_cache.invalidate()
        logger.info("Cache invalidated")
        return {
            "status": "ok",
            "message": "Cache invalidated, will rebuild on next access"
        }
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )

