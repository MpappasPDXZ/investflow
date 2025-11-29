#!/usr/bin/env python3
"""
Simple script to view users from PostgreSQL database
"""
import sys
from sqlalchemy import text
from app.core.database import get_engine
from app.core.logging import get_logger

logger = get_logger(__name__)

def view_users(limit: int = 10):
    """View users from PostgreSQL"""
    try:
        engine = get_engine()
        
        print(f"\n📊 Querying PostgreSQL users table")
        print("=" * 80)
        
        with engine.connect() as conn:
            # Get total count
            count_result = conn.execute(text("SELECT COUNT(*) FROM users"))
            total = count_result.scalar()
            
            print(f"\n✅ Found {total} user(s) in PostgreSQL")
            
            if total > 0:
                # Get users
                query = text("""
                    SELECT 
                        id, 
                        email, 
                        first_name, 
                        last_name, 
                        name,
                        is_active, 
                        created_at, 
                        updated_at
                    FROM users 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                """)
                result = conn.execute(query, {"limit": limit})
                users = result.fetchall()
                
                print(f"\n📋 Showing {len(users)} user(s):")
                print("-" * 80)
                
                for i, user in enumerate(users, 1):
                    print(f"\n--- User {i} ---")
                    print(f"  id                           : {user.id}")
                    print(f"  email                        : {user.email}")
                    print(f"  first_name                   : {user.first_name}")
                    print(f"  last_name                    : {user.last_name}")
                    print(f"  name                         : {user.name}")
                    print(f"  is_active                    : {user.is_active}")
                    print(f"  created_at                   : {user.created_at}")
                    print(f"  updated_at                   : {user.updated_at}")
            else:
                print("\n⚠️  No users found in PostgreSQL")
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Failed to view users: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    view_users(limit)

