#!/usr/bin/env python3
"""
Run migration to add interest rate columns to users table
"""
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_db
from sqlalchemy import text

def run_migration():
    """Run the interest rate migration"""
    print("🚀 Starting interest rate migration...")
    
    # Read the migration SQL file
    migration_file = Path(__file__).parent / "add_user_interest_rates.sql"
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    # Execute the migration
    db = next(get_db())
    try:
        print("📝 Executing migration SQL...")
        db.execute(text(migration_sql))
        db.commit()
        print("✅ Migration completed successfully!")
        print("\nAdded columns:")
        print("  - mortgage_interest_rate (NUMERIC(5,4))")
        print("  - loc_interest_rate (NUMERIC(5,4))")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()

