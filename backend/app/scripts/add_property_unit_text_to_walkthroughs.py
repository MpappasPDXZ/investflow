#!/usr/bin/env python3
"""
Migration script to add property_display_name and unit_number columns to walkthroughs table.

This denormalizes property and unit text for faster queries without joins.
"""
import sys
from pathlib import Path
import pandas as pd

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table, read_table, read_table_filtered, upsert_data, append_data
from pyiceberg.expressions import EqualTo
from pyiceberg.types import StringType

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
WALKTHROUGHS_TABLE = "walkthroughs"
PROPERTIES_TABLE = "properties"
UNITS_TABLE = "units"


def add_property_unit_text_columns():
    """Add property_display_name and unit_number columns to walkthroughs table"""
    logger.info("🔄 Adding property_display_name and unit_number columns to walkthroughs table...")
    
    try:
        catalog = get_catalog()
        
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            logger.error(f"  ❌ Table {WALKTHROUGHS_TABLE} does not exist!")
            return False
        
        table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        current_schema = table.schema()
        
        # Check if columns already exist
        existing_fields = {field.name for field in current_schema.fields}
        has_property_display_name = "property_display_name" in existing_fields
        has_unit_number = "unit_number" in existing_fields
        
        if has_property_display_name and has_unit_number:
            logger.info("  ⏭️  property_display_name and unit_number columns already exist")
            # Still run backfill in case there are walkthroughs that need updating
            logger.info("  🔄 Backfilling existing walkthroughs...")
            backfill_walkthroughs()
            return True
        
        # Add the columns
        with table.update_schema() as update:
            if not has_property_display_name:
                logger.info("  ➕ Adding property_display_name column...")
                update.add_column("property_display_name", StringType(), required=False)
            if not has_unit_number:
                logger.info("  ➕ Adding unit_number column...")
                update.add_column("unit_number", StringType(), required=False)
        
        logger.info("  ✅ Columns added successfully")
        
        # Reload table to get updated schema
        table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        
        # Backfill existing data
        logger.info("  🔄 Backfilling existing walkthroughs...")
        backfill_walkthroughs()
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Error adding columns: {e}", exc_info=True)
        raise


def backfill_walkthroughs():
    """Backfill property_display_name and unit_number for existing walkthroughs"""
    try:
        # Read all walkthroughs
        walkthroughs_df = read_table(NAMESPACE, WALKTHROUGHS_TABLE)
        
        if len(walkthroughs_df) == 0:
            logger.info("  ⏭️  No walkthroughs to backfill")
            return
        
        # Read properties table
        if not table_exists(NAMESPACE, PROPERTIES_TABLE):
            logger.warning("  ⚠️  Properties table does not exist, skipping backfill")
            return
        
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        
        # Read units table if it exists
        units_df = None
        if table_exists(NAMESPACE, UNITS_TABLE):
            units_df = read_table(NAMESPACE, UNITS_TABLE)
        
        updated_count = 0
        for idx, walkthrough in walkthroughs_df.iterrows():
            property_id = str(walkthrough.get("property_id", ""))
            unit_id = str(walkthrough.get("unit_id", "")) if walkthrough.get("unit_id") else None
            
            # Get property display_name
            property_display_name = None
            if property_id:
                property_rows = properties_df[properties_df["id"] == property_id]
                if len(property_rows) > 0:
                    prop = property_rows.iloc[0]
                    property_display_name = prop.get("display_name") or prop.get("address", "")
                    if prop.get("city") or prop.get("state"):
                        if not property_display_name:
                            property_display_name = prop.get("address", "")
                        if prop.get("city"):
                            property_display_name += f", {prop.get('city', '')}"
                        if prop.get("state"):
                            property_display_name += f", {prop.get('state', '')}"
            
            # Get unit_number
            unit_number = None
            if unit_id and units_df is not None:
                unit_rows = units_df[units_df["id"] == unit_id]
                if len(unit_rows) > 0:
                    unit_number = unit_rows.iloc[0].get("unit_number", "")
            
            # Update if values changed
            if (walkthrough.get("property_display_name") != property_display_name or 
                walkthrough.get("unit_number") != unit_number):
                walkthrough_dict = walkthrough.to_dict()
                walkthrough_dict["property_display_name"] = property_display_name
                walkthrough_dict["unit_number"] = unit_number
                walkthrough_dict["updated_at"] = pd.Timestamp.now()
                
                # Update the walkthrough using delete + append (more reliable than upsert with schema changes)
                update_df = pd.DataFrame([walkthrough_dict])
                # Reload table to ensure we have the latest schema
                table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
                schema_columns = [field.name for field in table.schema().fields]
                update_df = update_df.reindex(columns=schema_columns, fill_value=None)
                
                # Delete old row and append new one
                from pyiceberg.expressions import EqualTo
                table.delete(EqualTo("id", walkthrough_dict["id"]))
                append_data(NAMESPACE, WALKTHROUGHS_TABLE, update_df)
                updated_count += 1
        
        logger.info(f"  ✅ Backfilled {updated_count} walkthroughs")
        
    except Exception as e:
        logger.error(f"  ❌ Error backfilling walkthroughs: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        success = add_property_unit_text_columns()
        if success:
            logger.info("\n✅ Migration complete!")
        else:
            logger.info("\n❌ Migration failed!")
    except Exception as e:
        logger.error(f"\n❌ Migration error: {e}", exc_info=True)
        sys.exit(1)

