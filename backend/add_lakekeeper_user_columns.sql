-- Add Lakekeeper-required columns to users table
-- This migration adds the columns that Lakekeeper expects
-- NOTE: Lakekeeper requires the id column to be TEXT, not UUID

-- 0. Convert id column from UUID to TEXT (required by Lakekeeper)
-- This is a complex operation that requires dropping and recreating foreign keys
-- Only run if id column is currently UUID type

DO $$
DECLARE
    id_type text;
BEGIN
    -- Check current type of id column
    SELECT data_type INTO id_type
    FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'id';
    
    -- Only convert if it's UUID
    IF id_type = 'uuid' THEN
        -- Step 0a: Drop foreign key constraints that reference users.id
        ALTER TABLE IF EXISTS properties DROP CONSTRAINT IF EXISTS properties_user_id_fkey;
        ALTER TABLE IF EXISTS scenarios DROP CONSTRAINT IF EXISTS scenarios_user_id_fkey;
        ALTER TABLE IF EXISTS expenses DROP CONSTRAINT IF EXISTS expenses_created_by_user_id_fkey;
        ALTER TABLE IF EXISTS rents DROP CONSTRAINT IF EXISTS rents_created_by_user_id_fkey;
        ALTER TABLE IF EXISTS document_storage DROP CONSTRAINT IF EXISTS document_storage_uploaded_by_user_id_fkey;
        
        -- Step 0b: Add temporary text columns
        ALTER TABLE users ADD COLUMN IF NOT EXISTS id_text TEXT;
        ALTER TABLE properties ADD COLUMN IF NOT EXISTS user_id_text TEXT;
        ALTER TABLE scenarios ADD COLUMN IF NOT EXISTS user_id_text TEXT;
        ALTER TABLE expenses ADD COLUMN IF NOT EXISTS created_by_user_id_text TEXT;
        ALTER TABLE rents ADD COLUMN IF NOT EXISTS created_by_user_id_text TEXT;
        ALTER TABLE document_storage ADD COLUMN IF NOT EXISTS uploaded_by_user_id_text TEXT;
        
        -- Step 0c: Populate text columns from UUID columns
        UPDATE users SET id_text = id::text WHERE id_text IS NULL;
        UPDATE properties SET user_id_text = user_id::text WHERE user_id_text IS NULL;
        UPDATE scenarios SET user_id_text = user_id::text WHERE user_id_text IS NULL;
        UPDATE expenses SET created_by_user_id_text = created_by_user_id::text WHERE created_by_user_id_text IS NULL;
        UPDATE rents SET created_by_user_id_text = created_by_user_id::text WHERE created_by_user_id_text IS NULL;
        UPDATE document_storage SET uploaded_by_user_id_text = uploaded_by_user_id::text WHERE uploaded_by_user_id_text IS NULL;
        
        -- Step 0d: Drop old UUID columns and constraints
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey;
        ALTER TABLE users DROP COLUMN IF EXISTS id;
        ALTER TABLE properties DROP COLUMN IF EXISTS user_id;
        ALTER TABLE scenarios DROP COLUMN IF EXISTS user_id;
        ALTER TABLE expenses DROP COLUMN IF EXISTS created_by_user_id;
        ALTER TABLE rents DROP COLUMN IF EXISTS created_by_user_id;
        ALTER TABLE document_storage DROP COLUMN IF EXISTS uploaded_by_user_id;
        
        -- Step 0e: Rename text columns to original names
        ALTER TABLE users RENAME COLUMN id_text TO id;
        ALTER TABLE properties RENAME COLUMN user_id_text TO user_id;
        ALTER TABLE scenarios RENAME COLUMN user_id_text TO user_id;
        ALTER TABLE expenses RENAME COLUMN created_by_user_id_text TO created_by_user_id;
        ALTER TABLE rents RENAME COLUMN created_by_user_id_text TO created_by_user_id;
        ALTER TABLE document_storage RENAME COLUMN uploaded_by_user_id_text TO uploaded_by_user_id;
        
        -- Step 0f: Add primary key and foreign key constraints back
        ALTER TABLE users ADD PRIMARY KEY (id);
        ALTER TABLE properties ADD CONSTRAINT properties_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        ALTER TABLE scenarios ADD CONSTRAINT scenarios_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        ALTER TABLE expenses ADD CONSTRAINT expenses_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE rents ADD CONSTRAINT rents_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE document_storage ADD CONSTRAINT document_storage_uploaded_by_user_id_fkey FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

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
-- Also handle reverse: if name is provided but first_name/last_name are null, split name
CREATE OR REPLACE FUNCTION sync_user_name()
RETURNS TRIGGER AS $$
BEGIN
    -- If name is provided but first_name or last_name is null, split name
    IF NEW.name IS NOT NULL AND (NEW.first_name IS NULL OR NEW.last_name IS NULL) THEN
        -- Split name into first_name and last_name
        -- Simple split: take first word as first_name, rest as last_name
        DECLARE
            name_parts TEXT[];
        BEGIN
            name_parts := string_to_array(TRIM(NEW.name), ' ');
            IF array_length(name_parts, 1) >= 2 THEN
                NEW.first_name := name_parts[1];
                NEW.last_name := array_to_string(name_parts[2:], ' ');
            ELSIF array_length(name_parts, 1) = 1 THEN
                NEW.first_name := name_parts[1];
                NEW.last_name := '';  -- Empty string if only one word
            END IF;
        END;
    END IF;
    
    -- Always sync name from first_name and last_name (in case they were updated)
    NEW.name = TRIM(COALESCE(NEW.first_name, '') || ' ' || COALESCE(NEW.last_name, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sync_user_name_trigger ON users;
CREATE TRIGGER sync_user_name_trigger
    BEFORE INSERT OR UPDATE OF first_name, last_name, name ON users
    FOR EACH ROW
    EXECUTE FUNCTION sync_user_name();

