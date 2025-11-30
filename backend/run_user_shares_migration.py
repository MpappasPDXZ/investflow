#!/usr/bin/env python3
"""
Run migration to create user_shares table for bidirectional property sharing
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_db
from sqlalchemy import text

def run_migration():
    """Run the user_shares table migration"""
    print("🚀 Starting user_shares table migration...")
    
    migration_file = Path(__file__).parent / "add_user_shares_table.sql"
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    db = next(get_db())
    try:
        print("📝 Executing migration SQL...")
        db.execute(text(migration_sql))
        db.commit()
        print("✅ Migration completed successfully!")
        print("\nCreated:")
        print("  - user_shares table")
        print("  - Indexes for fast lookups")
        print("\n💡 Bidirectional sharing: When A adds B, both can see each other's properties")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()

