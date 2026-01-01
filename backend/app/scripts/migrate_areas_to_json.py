#!/usr/bin/env python3
"""
Migration script to migrate existing walkthrough areas from separate table to areas_json column.

This script:
1. Backs up walkthroughs data to local parquet file
2. Drops and recreates the walkthroughs table with areas_json column
3. Migrates areas from walkthrough_areas table to areas_json column
4. Restores walkthroughs data with areas_json populated
"""
import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import pyarrow as pa

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table, read_table, append_data
from pyiceberg.expressions import EqualTo

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
WALKTHROUGHS_TABLE = "walkthroughs"
WALKTHROUGH_AREAS_TABLE = "walkthrough_areas"


def create_walkthroughs_schema() -> pa.Schema:
    """Create PyArrow schema for walkthroughs table with areas_json column"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("unit_id", pa.string(), nullable=True),
        pa.field("property_display_name", pa.string(), nullable=True),
        pa.field("unit_number", pa.string(), nullable=True),
        pa.field("walkthrough_type", pa.string(), nullable=False),
        pa.field("walkthrough_date", pa.date32(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("inspector_name", pa.string(), nullable=True),
        pa.field("tenant_name", pa.string(), nullable=True),
        pa.field("tenant_signed", pa.bool_(), nullable=False),
        pa.field("tenant_signature_date", pa.date32(), nullable=True),
        pa.field("landlord_signed", pa.bool_(), nullable=False),
        pa.field("landlord_signature_date", pa.date32(), nullable=True),
        pa.field("overall_condition", pa.string(), nullable=False),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("generated_pdf_blob_name", pa.string(), nullable=True),
        pa.field("areas_json", pa.string(), nullable=True),  # NEW: JSON column for areas
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


def migrate_areas_to_json():
    """Migrate existing areas from separate table to areas_json column"""
    logger.info("🔄 Starting migration of areas to areas_json column...")
    
    try:
        catalog = get_catalog()
        
        # Check if tables exist
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            logger.error(f"  ❌ Table {WALKTHROUGHS_TABLE} does not exist!")
            return False
        
        # Step 1: Backup walkthroughs data to parquet
        logger.info("  💾 Step 1: Backing up walkthroughs data to parquet...")
        walkthroughs_df = read_table(NAMESPACE, WALKTHROUGHS_TABLE)
        logger.info(f"  ✅ Found {len(walkthroughs_df)} walkthroughs")
        
        backup_file = f"/tmp/walkthroughs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        walkthroughs_df.to_parquet(backup_file, index=False)
        logger.info(f"  ✅ Backup saved to: {backup_file}")
        
        # Step 2: Read areas data if table exists
        areas_by_walkthrough = {}
        if table_exists(NAMESPACE, WALKTHROUGH_AREAS_TABLE):
            logger.info("  📖 Step 2: Reading areas from walkthrough_areas table...")
            areas_df = read_table(NAMESPACE, WALKTHROUGH_AREAS_TABLE)
            logger.info(f"  ✅ Found {len(areas_df)} areas")
            
            # Group areas by walkthrough_id
            for _, area in areas_df.iterrows():
                walkthrough_id = area["walkthrough_id"]
                if walkthrough_id not in areas_by_walkthrough:
                    areas_by_walkthrough[walkthrough_id] = []
                areas_by_walkthrough[walkthrough_id].append(area)
        else:
            logger.info("  ⏭️  No walkthrough_areas table found - will create empty areas_json")
        
        # Step 3: Convert areas to JSON format for each walkthrough
        logger.info("  🔄 Step 3: Converting areas to JSON format...")
        for _, walkthrough in walkthroughs_df.iterrows():
            walkthrough_id = walkthrough["id"]
            areas = areas_by_walkthrough.get(walkthrough_id, [])
            
            if len(areas) == 0:
                walkthrough["areas_json"] = None
                continue
            
            # Convert areas to JSON format
            areas_json_data = []
            for area in areas:
                # Parse issues if present
                issues = []
                if area.get("issues"):
                    try:
                        issues = json.loads(area["issues"])
                    except:
                        pass
                
                # Parse photos if present
                photos = []
                if area.get("photos"):
                    try:
                        photos = json.loads(area["photos"])
                    except:
                        pass
                
                area_json = {
                    "id": area["id"],
                    "floor": area["floor"],
                    "area_name": area["area_name"],
                    "area_order": int(area.get("area_order", 0)),
                    "inspection_status": area.get("inspection_status", "no_issues"),
                    "notes": area.get("notes"),
                    "landlord_fix_notes": area.get("landlord_fix_notes"),
                    "issues": issues,
                    "photos": photos
                }
                areas_json_data.append(area_json)
            
            # Sort by area_order
            areas_json_data.sort(key=lambda x: x.get("area_order", 0))
            
            # Add areas_json to walkthrough
            walkthrough["areas_json"] = json.dumps(areas_json_data)
        
        # Step 4: Drop and recreate table with new schema
        logger.info("  🔄 Step 4: Dropping and recreating walkthroughs table...")
        walkthroughs_identifier = (*NAMESPACE, WALKTHROUGHS_TABLE)
        
        try:
            catalog.drop_table(walkthroughs_identifier)
            logger.info("  ✅ Dropped existing table")
        except Exception as e:
            logger.warning(f"  ⚠️  Could not drop table (may not exist): {e}")
        
        schema = create_walkthroughs_schema()
        catalog.create_table(identifier=walkthroughs_identifier, schema=schema)
        logger.info("  ✅ Created new table with areas_json column")
        
        # Step 5: Restore data with areas_json
        logger.info("  📤 Step 5: Restoring walkthroughs data with areas_json...")
        
        # Ensure areas_json column exists in DataFrame
        if "areas_json" not in walkthroughs_df.columns:
            walkthroughs_df["areas_json"] = None
        
        # Convert date columns to date type (not datetime)
        date_columns = ["walkthrough_date", "tenant_signature_date", "landlord_signature_date"]
        for col in date_columns:
            if col in walkthroughs_df.columns:
                walkthroughs_df[col] = pd.to_datetime(walkthroughs_df[col]).dt.date
        
        # Ensure timestamp columns are datetime
        timestamp_columns = ["created_at", "updated_at"]
        for col in timestamp_columns:
            if col in walkthroughs_df.columns:
                walkthroughs_df[col] = pd.to_datetime(walkthroughs_df[col])
        
        # Append data (append_data will handle schema conversion)
        append_data(NAMESPACE, WALKTHROUGHS_TABLE, walkthroughs_df)
        logger.info(f"  ✅ Restored {len(walkthroughs_df)} walkthroughs with areas_json")
        
        # Count how many have areas_json
        areas_json_count = walkthroughs_df["areas_json"].notna().sum()
        logger.info(f"  📊 {areas_json_count} walkthroughs have areas_json populated")
        
        logger.info(f"\n✅ Migration complete!")
        logger.info(f"  💾 Backup file: {backup_file}")
        logger.info(f"  📊 Migrated: {len(walkthroughs_df)} walkthroughs")
        logger.info(f"  📊 Areas migrated: {sum(len(areas_by_walkthrough.get(wid, [])) for wid in walkthroughs_df['id'])} areas")
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Error migrating areas: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        success = migrate_areas_to_json()
        if success:
            logger.info("\n✅ Migration complete!")
        else:
            logger.info("\n❌ Migration failed!")
    except Exception as e:
        logger.error(f"\n❌ Migration error: {e}", exc_info=True)
        sys.exit(1)

