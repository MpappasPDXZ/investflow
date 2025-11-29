#!/usr/bin/env python3
"""
Run the Lakekeeper user columns migration
"""
import sys
from pathlib import Path
from app.core.database import get_engine
from app.core.logging import get_logger

logger = get_logger(__name__)

def run_migration():
    """Run the migration SQL file"""
    migration_file = Path(__file__).parent / "add_lakekeeper_user_columns.sql"
    
    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        sys.exit(1)
    
    logger.info(f"Reading migration file: {migration_file}")
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    engine = get_engine()
    
    logger.info("Executing migration...")
    try:
        with engine.begin() as conn:  # begin() handles transaction and commit
            # Execute the SQL using text() for raw SQL
            from sqlalchemy import text
            conn.execute(text(sql))
        logger.info("✅ Migration completed successfully!")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run_migration()

