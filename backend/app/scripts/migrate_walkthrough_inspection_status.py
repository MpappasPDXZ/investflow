"""
Migration script to update walkthrough_areas table:
- Replace `condition` field with `inspection_status`
- Add `landlord_fix_notes` field

Migration logic:
- excellent/good → no_issues
- fair/poor → issue_noted_as_is (if no notes) or issue_landlord_to_fix (if notes exist)
- If notes exist for fair/poor, move to landlord_fix_notes
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.iceberg import get_catalog, read_table, table_exists, NAMESPACE
from app.core.logging import get_logger

logger = get_logger(__name__)

TABLE_NAME = "walkthrough_areas"


def migrate_condition_to_inspection_status(condition: str, notes: str) -> tuple[str, str]:
    """
    Map old condition to new inspection_status and landlord_fix_notes

    Returns:
        (inspection_status, landlord_fix_notes)
    """
    condition_lower = (condition or "").lower()
    notes = notes or ""
    has_notes = bool(notes.strip())

    if condition_lower in ["excellent", "good"]:
        return ("no_issues", "")
    elif condition_lower in ["fair", "poor"]:
        if has_notes:
            # If there are notes, assume landlord will fix
            return ("issue_landlord_to_fix", notes)
        else:
            # No notes, assume leaving as-is
            return ("issue_noted_as_is", "")
    else:
        # Default to no_issues for unknown values
        return ("no_issues", "")


def migrate_walkthrough_areas():
    """Migrate walkthrough_areas table to new schema"""
    logger.info("🔄 Starting walkthrough_areas migration...")

    try:
        catalog = get_catalog()

        # Check if table exists
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.warning(f"  ⚠️  Table {TABLE_NAME} does not exist. Skipping migration.")
            return

        logger.info(f"  📖 Reading existing {TABLE_NAME} data...")
        df = read_table(NAMESPACE, TABLE_NAME)

        if len(df) == 0:
            logger.info(f"  ✅ Table {TABLE_NAME} is empty. No migration needed.")
            return

        logger.info(f"  📊 Found {len(df)} rows to migrate")

        # Check if migration already done (has inspection_status column)
        if 'inspection_status' in df.columns:
            logger.info(f"  ✅ Table {TABLE_NAME} already has inspection_status column. Migration may have already been done.")
            # Check if old condition column still exists
            if 'condition' in df.columns:
                logger.warning(f"  ⚠️  Old 'condition' column still exists. Consider removing it manually.")
            return

        # Check if condition column exists
        if 'condition' not in df.columns:
            logger.warning(f"  ⚠️  Table {TABLE_NAME} does not have 'condition' column. Cannot migrate.")
            return

        # Apply migration logic
        logger.info("  🔄 Applying migration logic...")
        migration_results = df.apply(
            lambda row: migrate_condition_to_inspection_status(
                row.get('condition', ''),
                row.get('notes', '')
            ),
            axis=1,
            result_type='expand'
        )
        migration_results.columns = ['inspection_status', 'landlord_fix_notes']

        # Add new columns
        df['inspection_status'] = migration_results['inspection_status']
        df['landlord_fix_notes'] = migration_results['landlord_fix_notes']

        # If notes were moved to landlord_fix_notes, clear the general notes
        # (only for items that became issue_landlord_to_fix)
        mask_landlord_fix = df['inspection_status'] == 'issue_landlord_to_fix'
        if mask_landlord_fix.any():
            # Keep original notes in general notes field for reference
            # Actually, let's keep both - general notes can have additional context
            pass

        # Drop old condition column
        if 'condition' in df.columns:
            df = df.drop(columns=['condition'])

        logger.info("  📊 Migration summary:")
        logger.info(f"    - no_issues: {len(df[df['inspection_status'] == 'no_issues'])}")
        logger.info(f"    - issue_noted_as_is: {len(df[df['inspection_status'] == 'issue_noted_as_is'])}")
        logger.info(f"    - issue_landlord_to_fix: {len(df[df['inspection_status'] == 'issue_landlord_to_fix'])}")

        # Save to parquet for backup
        backup_file = f"/tmp/walkthrough_areas_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        logger.info(f"  💾 Creating backup: {backup_file}")
        df.to_parquet(backup_file, index=False)
        logger.info(f"  ✅ Backup saved to {backup_file}")

        # Note: This script only prepares the data
        # The actual table schema update should be done via:
        # 1. Backup data (done above)
        # 2. Drop and recreate table with new schema
        # 3. Append migrated data

        logger.info("  ⚠️  NOTE: This script prepares the data migration.")
        logger.info("  ⚠️  You need to:")
        logger.info("     1. Drop the existing walkthrough_areas table")
        logger.info("     2. Recreate it with the new schema (inspection_status, landlord_fix_notes)")
        logger.info("     3. Append the migrated data from the backup parquet file")
        logger.info(f"  📁 Backup file location: {backup_file}")

        return backup_file

    except Exception as e:
        logger.error(f"  ❌ Error migrating {TABLE_NAME}: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        backup_file = migrate_walkthrough_areas()
        if backup_file:
            logger.info(f"\n✅ Migration preparation complete!")
            logger.info(f"📁 Backup saved to: {backup_file}")
        else:
            logger.info("\n✅ No migration needed.")
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)




