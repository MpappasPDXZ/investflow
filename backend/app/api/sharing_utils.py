"""Helper functions for property sharing - using Iceberg tables"""
from typing import List
import pandas as pd
from app.core.iceberg import read_table, table_exists
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = ("investflow",)
USERS_TABLE = "users"
SHARES_TABLE = "user_shares"


def get_shared_user_ids(current_user_id: str, current_user_email: str) -> List[str]:
    """
    Get list of user IDs that have bidirectional sharing with the current user.
    
    Returns:
        List of user IDs where:
        - Current user has shared with them (we added their email)
        - They have shared with us (they added our email)
    """
    try:
        if not table_exists(NAMESPACE, SHARES_TABLE):
            return []
        
        shares_df = read_table(NAMESPACE, SHARES_TABLE)
        
        if len(shares_df) == 0:
            return []
        
        users_df = read_table(NAMESPACE, USERS_TABLE)
        
        shared_user_ids = set()
        
        # Find users where we added their email
        our_shares = shares_df[shares_df["user_id"] == current_user_id]
        if len(our_shares) > 0:
            # Get user IDs for those emails
            shared_emails = our_shares["shared_email"].tolist()
            matched_users = users_df[users_df["email"].isin(shared_emails)]
            shared_user_ids.update(matched_users["id"].tolist())
        
        # Find users who added our email
        shares_with_us = shares_df[shares_df["shared_email"] == current_user_email]
        if len(shares_with_us) > 0:
            shared_user_ids.update(shares_with_us["user_id"].tolist())
        
        result = list(shared_user_ids)
        logger.debug(f"User {current_user_id} has sharing with: {result}")
        
        return result
        
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
    
    Access is granted if:
    1. User owns the property, OR
    2. User has bidirectional share with the property owner
    """
    # User owns the property
    if property_user_id == current_user_id:
        return True
    
    # Check if there's a bidirectional share
    try:
        if not table_exists(NAMESPACE, SHARES_TABLE):
            return False
        
        shares_df = read_table(NAMESPACE, SHARES_TABLE)
        
        if len(shares_df) == 0:
            return False
        
        # Get property owner's email
        users_df = read_table(NAMESPACE, USERS_TABLE)
        owner_rows = users_df[users_df["id"] == property_user_id]
        
        if len(owner_rows) == 0:
            return False
        
        property_owner_email = owner_rows.iloc[0]["email"]
        
        # Check if current user shared with property owner's email
        current_user_shared = shares_df[
            (shares_df["user_id"] == current_user_id) & 
            (shares_df["shared_email"] == property_owner_email)
        ]
        
        if len(current_user_shared) > 0:
            logger.debug(f"User {current_user_id} has access (shared with owner)")
            return True
        
        # Check if property owner shared with current user's email
        owner_shared = shares_df[
            (shares_df["user_id"] == property_user_id) & 
            (shares_df["shared_email"] == current_user_email)
        ]
        
        if len(owner_shared) > 0:
            logger.debug(f"User {current_user_id} has access (owner shared with them)")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking property access: {e}", exc_info=True)
        return False


