"""Helper functions for property sharing - using CDC cache for fast lookups"""
from typing import List
from app.core.logging import get_logger
from app.services.auth_cache_service import auth_cache

logger = get_logger(__name__)


def get_shared_user_ids(current_user_id: str, current_user_email: str) -> List[str]:
    """
    Get list of user IDs that have bidirectional sharing with the current user.
    Uses CDC cache for O(1) lookups.
    
    Returns:
        List of user IDs where:
        - Current user has shared with them (we added their email)
        - They have shared with us (they added our email)
    """
    try:
        return auth_cache.get_shared_user_ids(current_user_id, current_user_email)
    except Exception as e:
        logger.error(f"Error getting shared user IDs: {e}", exc_info=True)
        return []


def user_has_property_access(
    property_user_id: str,
    current_user_id: str,
    current_user_email: str
) -> bool:
    """
    Check if current user has access to a property.
    Uses CDC cache for O(1) lookups.
    
    Access is granted if:
    1. User owns the property, OR
    2. User has share relationship with the property owner
    """
    try:
        return auth_cache.user_has_property_access(
            property_user_id,
            current_user_id,
            current_user_email
        )
    except Exception as e:
        logger.error(f"Error checking property access: {e}", exc_info=True)
        return False


