-- Add Lakekeeper-required columns to users table
-- This migration adds the columns that Lakekeeper expects

-- 1. Add the 'name' column (computed from first_name and last_name)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS name TEXT;

-- 2. Populate name from first_name and last_name for existing users
UPDATE users 
SET name = TRIM(first_name || ' ' || last_name)
WHERE name IS NULL;

-- 3. Make name NOT NULL after populating
ALTER TABLE users 
ALTER COLUMN name SET NOT NULL;

-- 4. Add Lakekeeper-specific columns
DO $$ 
BEGIN
    -- Create enum types if they don't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_type') THEN
        CREATE TYPE user_type AS ENUM ('application', 'human');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_last_updated_with') THEN
        CREATE TYPE user_last_updated_with AS ENUM ('create-endpoint', 'config-call-creation', 'update-endpoint');
    END IF;
END $$;

-- 5. Add Lakekeeper columns
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS user_type user_type DEFAULT 'human' NOT NULL,
ADD COLUMN IF NOT EXISTS last_updated_with user_last_updated_with DEFAULT 'create-endpoint' NOT NULL,
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- 6. Create index on name for Lakekeeper searches
CREATE INDEX IF NOT EXISTS users_name_gist_idx ON users USING gist (name gist_trgm_ops(siglen=256));

-- 7. Create trigger to keep name in sync with first_name and last_name
CREATE OR REPLACE FUNCTION sync_user_name()
RETURNS TRIGGER AS $$
BEGIN
    NEW.name = TRIM(COALESCE(NEW.first_name, '') || ' ' || COALESCE(NEW.last_name, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sync_user_name_trigger ON users;
CREATE TRIGGER sync_user_name_trigger
    BEFORE INSERT OR UPDATE OF first_name, last_name ON users
    FOR EACH ROW
    EXECUTE FUNCTION sync_user_name();

