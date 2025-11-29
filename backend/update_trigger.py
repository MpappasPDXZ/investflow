#!/usr/bin/env python3
"""Update the sync_user_name trigger to handle Lakekeeper user creation"""
from app.core.database import get_engine
from sqlalchemy import text

trigger_sql = """
DROP TRIGGER IF EXISTS sync_user_name_trigger ON users;

CREATE OR REPLACE FUNCTION sync_user_name()
RETURNS TRIGGER AS $$
BEGIN
    -- If name is provided but first_name or last_name is null, split name
    IF NEW.name IS NOT NULL AND TRIM(NEW.name) != '' AND (NEW.first_name IS NULL OR NEW.last_name IS NULL) THEN
        -- Split name into first_name and last_name
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
    
    -- Ensure first_name and last_name have defaults if still null
    IF NEW.first_name IS NULL THEN
        NEW.first_name := '';
    END IF;
    IF NEW.last_name IS NULL THEN
        NEW.last_name := '';
    END IF;
    
    -- Set default email if null (for Lakekeeper users)
    IF NEW.email IS NULL OR TRIM(NEW.email) = '' THEN
        -- Generate a default email based on name or id
        IF NEW.name IS NOT NULL AND TRIM(NEW.name) != '' THEN
            NEW.email := LOWER(REPLACE(TRIM(NEW.name), ' ', '.')) || '@lakekeeper.local';
        ELSIF NEW.id IS NOT NULL THEN
            NEW.email := NEW.id || '@lakekeeper.local';
        ELSE
            NEW.email := 'unknown@lakekeeper.local';
        END IF;
    END IF;
    
    -- Always sync name from first_name and last_name (in case they were updated)
    NEW.name = TRIM(COALESCE(NEW.first_name, '') || ' ' || COALESCE(NEW.last_name, ''));
    -- Ensure name is not empty (Lakekeeper requires it)
    IF TRIM(NEW.name) = '' THEN
        NEW.name := 'Unknown User';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sync_user_name_trigger
    BEFORE INSERT OR UPDATE OF first_name, last_name, name ON users
    FOR EACH ROW
    EXECUTE FUNCTION sync_user_name();
"""

if __name__ == "__main__":
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(trigger_sql))
    print("✅ Trigger updated successfully!")

