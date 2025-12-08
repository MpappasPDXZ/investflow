#!/usr/bin/env python3
"""
Reset Lakekeeper database tables to allow clean startup.
This drops all Lakekeeper-managed tables so Lakekeeper can recreate them.
Your Iceberg data in ADLS is NOT affected - only the catalog metadata.
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get PostgreSQL connection from environment"""
    db_url = os.getenv("LAKEKEEPER__PG_DATABASE_URL_WRITE")
    
    if not db_url:
        # Construct from individual variables
        user = os.getenv("POSTGRES_USER", "lakekeeper")
        password = os.getenv("POSTGRES_PASSWORD")
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "lakekeeper")
        
        if not password:
            print("❌ Missing database password!")
            sys.exit(1)
        
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=require"
    
    # Parse the connection string
    from urllib.parse import urlparse
    result = urlparse(db_url)
    
    return psycopg2.connect(
        host=result.hostname,
        port=result.port or 5432,
        user=result.username,
        password=result.password,
        database=result.path[1:],  # Remove leading /
        sslmode='require'
    )

def drop_lakekeeper_tables(confirm=False):
    """Drop all Lakekeeper tables"""
    print("=" * 70)
    print("Reset Lakekeeper Database")
    print("=" * 70)
    print()
    print("⚠️  This will drop all Lakekeeper catalog tables.")
    print("⚠️  Your data in ADLS is safe - only metadata will be removed.")
    print()
    
    if not confirm:
        response = input("Type 'YES' to continue: ")
        if response != "YES":
            print("❌ Aborted")
            sys.exit(0)
    
    print()
    print("Connecting to PostgreSQL...")
    
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Get all Lakekeeper tables
        print("Finding Lakekeeper tables...")
        cursor.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            AND tablename NOT LIKE 'pg_%'
            ORDER BY tablename;
        """)
        
        tables = cursor.fetchall()
        
        if not tables:
            print("✅ No tables found - database is clean")
            return
        
        print(f"Found {len(tables)} tables:")
        for (table,) in tables:
            print(f"  - {table}")
        
        print()
        print("Dropping tables...")
        
        # Drop tables in order (handle dependencies)
        for (table,) in tables:
            try:
                print(f"  Dropping {table}...", end=" ")
                cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                print("✅")
            except Exception as e:
                print(f"⚠️  {e}")
        
        # Drop sequences
        print()
        print("Dropping sequences...")
        cursor.execute("""
            SELECT sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public';
        """)
        sequences = cursor.fetchall()
        for (seq,) in sequences:
            try:
                print(f"  Dropping {seq}...", end=" ")
                cursor.execute(f'DROP SEQUENCE IF EXISTS "{seq}" CASCADE')
                print("✅")
            except Exception as e:
                print(f"⚠️  {e}")
        
        # Drop collations (case_insensitive if exists)
        print()
        print("Dropping collations...")
        cursor.execute("""
            SELECT collname 
            FROM pg_collation 
            WHERE collnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
        """)
        collations = cursor.fetchall()
        for (coll,) in collations:
            try:
                print(f"  Dropping {coll}...", end=" ")
                cursor.execute(f'DROP COLLATION IF EXISTS "{coll}" CASCADE')
                print("✅")
            except Exception as e:
                print(f"⚠️  {e}")
        
        cursor.close()
        conn.close()
        
        print()
        print("=" * 70)
        print("✅ Database reset complete!")
        print()
        print("Next steps:")
        print("1. Restart containers: cd backend && docker-compose up --build -d")
        print("2. Lakekeeper will recreate its schema automatically")
        print("3. Your Iceberg tables in ADLS are untouched")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import sys
    confirm = "--confirm" in sys.argv
    drop_lakekeeper_tables(confirm=confirm)

