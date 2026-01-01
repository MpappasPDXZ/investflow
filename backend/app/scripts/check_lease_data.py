#!/usr/bin/env python3
"""
Check lease data in the database to see if garage door fields are stored
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.logging import setup_logging, get_logger
from app.core.iceberg import read_table

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
LEASES_TABLE = "leases_full"

def check_lease_data():
    """Check lease data for 501 NE 67th Street"""
    logger.info("🔍 Checking lease data in database...")
    
    try:
        # Read all leases
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        
        # Use the property ID from the user's data
        property_id = "72144430-08ed-41de-b264-34af5181bd03"
        logger.info(f"\n📋 Looking for leases with property_id: {property_id}")
        
        # Get leases for this property
        lease_rows = leases_df[leases_df["property_id"] == str(property_id)]
        lease_rows = lease_rows[lease_rows["is_active"] == True]
        
        if len(lease_rows) == 0:
            logger.error("❌ No active leases found for this property")
            return
        
        logger.info(f"\n✅ Found {len(lease_rows)} active lease(s)")
        
        # Get the latest lease
        lease_rows = lease_rows.sort_values("updated_at", ascending=False)
        lease = lease_rows.iloc[0]
        
        logger.info(f"\n📄 Lease ID: {lease['id']}")
        logger.info(f"   Updated: {lease['updated_at']}")
        logger.info(f"   Version: {lease.get('lease_version', 'N/A')}")
        
        # Check the garage door fields
        logger.info(f"\n🔑 KEY FIELDS:")
        logger.info(f"   front_door_keys: {lease.get('front_door_keys')} (type: {type(lease.get('front_door_keys'))})")
        logger.info(f"   back_door_keys: {lease.get('back_door_keys')} (type: {type(lease.get('back_door_keys'))})")
        logger.info(f"   garage_back_door_keys: {lease.get('garage_back_door_keys')} (type: {type(lease.get('garage_back_door_keys'))})")
        logger.info(f"   key_replacement_fee: {lease.get('key_replacement_fee')} (type: {type(lease.get('key_replacement_fee'))})")
        
        logger.info(f"\n🚗 GARAGE DOOR OPENER FIELDS:")
        logger.info(f"   has_garage_door_opener: {lease.get('has_garage_door_opener')} (type: {type(lease.get('has_garage_door_opener'))})")
        logger.info(f"   garage_door_opener_fee: {lease.get('garage_door_opener_fee')} (type: {type(lease.get('garage_door_opener_fee'))})")
        
        # Check for NaN values
        import pandas as pd
        logger.info(f"\n🔍 NaN CHECK:")
        logger.info(f"   garage_back_door_keys is NaN: {pd.isna(lease.get('garage_back_door_keys'))}")
        logger.info(f"   has_garage_door_opener is NaN: {pd.isna(lease.get('has_garage_door_opener'))}")
        logger.info(f"   garage_door_opener_fee is NaN: {pd.isna(lease.get('garage_door_opener_fee'))}")
        
        # Show all columns to see what's available
        logger.info(f"\n📊 All columns in lease:")
        for col in lease.index:
            if 'garage' in col.lower() or 'door' in col.lower() or 'key' in col.lower():
                logger.info(f"   {col}: {lease[col]} (type: {type(lease[col])})")
        
    except Exception as e:
        logger.error(f"❌ Error checking lease data: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    check_lease_data()

