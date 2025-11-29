#!/usr/bin/env python3
"""Make first_name and last_name nullable or add defaults for Lakekeeper compatibility"""
from app.core.database import get_engine
from sqlalchemy import text

# Option 1: Make them nullable (simpler, but might break app logic)
# Option 2: Add default empty strings (better, maintains NOT NULL constraint)

fix_sql = """
-- Make first_name, last_name, and email nullable to allow Lakekeeper to create users
-- The trigger will populate first_name/last_name from name if provided
ALTER TABLE users 
ALTER COLUMN first_name DROP NOT NULL,
ALTER COLUMN last_name DROP NOT NULL,
ALTER COLUMN email DROP NOT NULL;

-- Add defaults as fallback
ALTER TABLE users 
ALTER COLUMN first_name SET DEFAULT '',
ALTER COLUMN last_name SET DEFAULT '',
ALTER COLUMN email SET DEFAULT '';

-- Remove unique constraint on email since it can be null/empty for Lakekeeper users
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key;
-- Recreate unique constraint that allows nulls (PostgreSQL treats nulls as distinct)
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON users (email) WHERE email IS NOT NULL AND email != '';
"""

if __name__ == "__main__":
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(fix_sql))
    print("✅ User schema updated - first_name and last_name are now nullable with defaults")

