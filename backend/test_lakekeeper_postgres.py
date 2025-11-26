#!/usr/bin/env python3
"""
Test script to verify Lakekeeper's PostgreSQL connection to Azure PostgreSQL.
This script tests the connection using the same parameters that Lakekeeper uses.
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse, quote_plus
from psycopg2 import sql
import json

def test_connection_from_env():
    """Test connection using environment variables from .env file"""
    print("=" * 60)
    print("Testing PostgreSQL Connection from Environment Variables")
    print("=" * 60)
    
    # Read from .env file if it exists
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    env_vars = {}
    
    if os.path.exists(env_file):
        print(f"\n📄 Reading from: {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    else:
        print(f"\n⚠️  .env file not found at {env_file}")
        print("   Using environment variables from current shell...")
        env_vars = dict(os.environ)
    
    # Get PostgreSQL connection parameters
    postgres_host = env_vars.get('POSTGRES_HOST', os.getenv('POSTGRES_HOST'))
    postgres_port = env_vars.get('POSTGRES_PORT', os.getenv('POSTGRES_PORT', '5432'))
    postgres_db = env_vars.get('POSTGRES_DB', os.getenv('POSTGRES_DB'))
    postgres_user = env_vars.get('POSTGRES_USER', os.getenv('POSTGRES_USER'))
    postgres_password = env_vars.get('POSTGRES_PASSWORD', os.getenv('POSTGRES_PASSWORD'))
    
    print(f"\n📋 Connection Parameters:")
    print(f"   Host: {postgres_host}")
    print(f"   Port: {postgres_port}")
    print(f"   Database: {postgres_db}")
    print(f"   User: {postgres_user}")
    print(f"   Password: {'*' * len(postgres_password) if postgres_password else 'NOT SET'}")
    
    if not all([postgres_host, postgres_db, postgres_user, postgres_password]):
        print("\n❌ ERROR: Missing required PostgreSQL connection parameters!")
        print("   Required: POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD")
        return False
    
    # Construct connection string (same format as Lakekeeper uses)
    connection_string = f"postgres://{postgres_user}:{quote_plus(postgres_password)}@{postgres_host}:{postgres_port}/{postgres_db}"
    
    print(f"\n🔗 Connection String (masked):")
    print(f"   postgres://{postgres_user}:***@{postgres_host}:{postgres_port}/{postgres_db}")
    
    return test_connection(connection_string, postgres_host, postgres_port, postgres_db, postgres_user, postgres_password)

def test_connection(connection_string, host, port, db, user, password):
    """Test the actual PostgreSQL connection"""
    print("\n" + "=" * 60)
    print("Testing Connection...")
    print("=" * 60)
    
    try:
        # Parse connection string
        parsed = urlparse(connection_string)
        
        # Connect using psycopg2
        print(f"\n🔌 Attempting to connect to {host}:{port}/{db}...")
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=db,
            user=user,
            password=password,
            connect_timeout=10,
            sslmode='require'  # Azure PostgreSQL requires SSL
        )
        
        print("✅ Connection successful!")
        
        # Test basic query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"\n📊 PostgreSQL Version: {version}")
        
        # Check if Lakekeeper tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'lakekeeper%'
            ORDER BY table_name;
        """)
        lakekeeper_tables = cursor.fetchall()
        
        if lakekeeper_tables:
            print(f"\n📋 Found {len(lakekeeper_tables)} Lakekeeper table(s):")
            for table in lakekeeper_tables:
                print(f"   - {table[0]}")
        else:
            print("\n⚠️  No Lakekeeper tables found. You may need to run migrations:")
            print("   docker-compose run --rm lakekeeper migrate")
        
        # Check database size and connection info
        cursor.execute("SELECT current_database(), current_user, inet_server_addr(), inet_server_port();")
        db_info = cursor.fetchone()
        print(f"\n📈 Database Info:")
        print(f"   Current Database: {db_info[0]}")
        print(f"   Current User: {db_info[1]}")
        print(f"   Server Address: {db_info[2] or 'N/A'}")
        print(f"   Server Port: {db_info[3] or 'N/A'}")
        
        # Test read and write capabilities
        print(f"\n🔍 Testing Read/Write Capabilities...")
        cursor.execute("SELECT 1 as test_read;")
        read_test = cursor.fetchone()
        if read_test:
            print("   ✅ Read test: PASSED")
        
        # Try to create a test table (will fail if no permissions, but that's ok)
        try:
            cursor.execute("CREATE TEMP TABLE test_write (id INT);")
            cursor.execute("INSERT INTO test_write VALUES (1);")
            cursor.execute("DROP TABLE test_write;")
            print("   ✅ Write test: PASSED")
        except Exception as e:
            print(f"   ⚠️  Write test: Limited permissions (this may be expected)")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ All connection tests PASSED!")
        print("=" * 60)
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Connection FAILED!")
        print(f"   Error: {str(e)}")
        print("\n💡 Common issues:")
        print("   - Firewall rules: Ensure your IP is allowed in Azure PostgreSQL firewall")
        print("   - SSL: Azure PostgreSQL requires SSL connections")
        print("   - Credentials: Verify username and password are correct")
        print("   - Network: Check if you can reach the PostgreSQL server")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_from_docker_container():
    """Test connection using the same connection string as the container"""
    print("\n" + "=" * 60)
    print("Testing Connection String from Docker Container")
    print("=" * 60)
    
    import subprocess
    
    try:
        # Get the connection string from the container
        result = subprocess.run(
            ['docker', 'inspect', 'lakekeeper-local', '--format={{range .Config.Env}}{{println .}}{{end}}'],
            capture_output=True,
            text=True,
            check=True
        )
        
        env_vars = {}
        for line in result.stdout.split('\n'):
            if 'LAKEKEEPER__PG_DATABASE_URL' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
        
        read_url = env_vars.get('LAKEKEEPER__PG_DATABASE_URL_READ')
        write_url = env_vars.get('LAKEKEEPER__PG_DATABASE_URL_WRITE')
        
        if read_url:
            print(f"\n📋 Container Connection String (READ):")
            # Mask password in output
            parsed = urlparse(read_url)
            masked = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}{parsed.path}"
            print(f"   {masked}")
            
            # Parse connection details
            parsed = urlparse(read_url)
            return test_connection(
                read_url,
                parsed.hostname,
                parsed.port or 5432,
                parsed.path.lstrip('/'),
                parsed.username,
                parsed.password
            )
        else:
            print("⚠️  Could not retrieve connection string from container")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Could not inspect container: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Lakekeeper PostgreSQL Connection Test")
    print("=" * 60)
    
    # Test 1: From environment variables
    result1 = test_connection_from_env()
    
    # Test 2: From Docker container
    result2 = test_from_docker_container()
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Environment Variables Test: {'✅ PASSED' if result1 else '❌ FAILED'}")
    print(f"Docker Container Test: {'✅ PASSED' if result2 else '❌ FAILED'}")
    
    if result1 or result2:
        print("\n✅ At least one connection method is working!")
        sys.exit(0)
    else:
        print("\n❌ All connection tests failed!")
        sys.exit(1)

