#!/usr/bin/env python3
"""Make password_hash nullable for Lakekeeper users"""
from app.core.database import get_engine
from sqlalchemy import text

fix_sql = """
-- Make password_hash nullable for Lakekeeper users (they don't have passwords)
ALTER TABLE users 
ALTER COLUMN password_hash DROP NOT NULL;
"""

if __name__ == "__main__":
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(fix_sql))
    print("✅ password_hash is now nullable")

