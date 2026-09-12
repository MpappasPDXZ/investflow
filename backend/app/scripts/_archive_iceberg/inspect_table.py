#!/usr/bin/env python3
"""
Interactive script to inspect contents of Iceberg tables.

IMPORTANT: This script must be run inside the Docker container:
    docker-compose exec backend python3 app/scripts/inspect_table.py

Or from the backend directory:
    cd backend && docker-compose exec backend python3 app/scripts/inspect_table.py

Usage:
    python inspect_table.py [--namespace NAMESPACE]
    
The script will:
1. Show a list of available tables
2. Let you select a table by number
3. Display top 10 rows and column dtypes
"""

import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

# Set up environment if running outside Docker (for development)
if not os.getenv('LAKEKEEPER__BASE_URI'):
    # Try to load from .env file
    env_file = backend_dir / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

from app.core.iceberg import get_catalog, read_table, load_table
import pandas as pd

def get_available_tables(namespace: tuple = ("investflow",)):
    """Get list of available tables in the namespace"""
    # Known tables - we'll verify they exist
    known_tables = [
        "leases",  # Lease management table (merged from leases_full and lease_tenants)
        "comps",  # Comparables table (rental comparables are stored here)
        "properties",
        "units",
        "tenants",
        "expenses",
        "rents",
        "walkthroughs",
        "users",  # Users table (cached via auth_cache_service CDC cache)
        "user_shares",  # User sharing table (cached via auth_cache_service CDC cache)
        "documents",
        "vault",  # Document storage table (used by document_service)
        "comparables",  # Legacy/alternative name (may not exist)
        "landlord_references",
        "scheduled_expenses",
        "scheduled_revenue"
    ]
    
    # Try to verify which tables actually exist
    existing_tables = []
    for table_name in known_tables:
        try:
            load_table(namespace, table_name)
            existing_tables.append(table_name)
        except Exception:
            # Table doesn't exist, skip it
            pass
    
    # If we found some tables, return them; otherwise return all known tables
    return existing_tables if existing_tables else known_tables

def format_value(val, max_len=50):
    """Format a value for display"""
    if pd.isna(val):
        return "NULL"
    if isinstance(val, (pd.Timestamp, pd.DatetimeTZDtype)):
        return str(val)
    if isinstance(val, float):
        if pd.isna(val):
            return "NULL"
        return f"{val:.2f}" if val % 1 != 0 else str(int(val))
    if isinstance(val, (list, dict)):
        val_str = str(val)
        return val_str[:max_len] + "..." if len(val_str) > max_len else val_str
    val_str = str(val)
    return val_str[:max_len] + "..." if len(val_str) > max_len else val_str

def inspect_table(table_name: str, namespace: tuple = ("investflow",), limit: int = 10):
    """Inspect and display table contents"""
    try:
        print(f"\n{'='*80}")
        print(f"Inspecting table: {'.'.join(namespace)}.{table_name}")
        print(f"{'='*80}\n")
        
        # Load table to get schema info
        table = load_table(namespace, table_name)
        schema = table.schema()
        
        print(f"Schema: {len(schema.fields)} columns\n")
        
        # Read table data
        print("Reading table data...")
        df = read_table(namespace, table_name)
        
        print(f"Total rows: {len(df)}\n")
        
        if len(df) == 0:
            print("Table is empty.")
            print(f"\nColumn dtypes:")
            for field in schema.fields:
                print(f"  {field.name:30s} {str(field.field_type):20s}")
            return
        
        print(f"{'='*80}")
        print(f"LAST RECORD (Most recently entered):")
        print(f"{'='*80}\n")
        
        # Get the last record (most recently entered - highest created_at or updated_at)
        if 'created_at' in df.columns:
            last_record = df.sort_values('created_at', ascending=False).iloc[0]
        elif 'updated_at' in df.columns:
            last_record = df.sort_values('updated_at', ascending=False).iloc[0]
        else:
            # If no timestamp columns, just get the last row
            last_record = df.iloc[-1]
        
        # Sort fields by dtype (easiest to convert first)
        def get_dtype_priority(field, df):
            """Get priority for sorting: object=1, bool=2, int=3, float=4, datetime=5"""
            if field.name in df.columns:
                pandas_dtype = str(df[field.name].dtype)
            else:
                pandas_dtype = str(field.field_type)
            
            dtype_lower = pandas_dtype.lower()
            if 'object' in dtype_lower or 'string' in dtype_lower:
                return 1
            elif 'bool' in dtype_lower:
                return 2
            elif 'int' in dtype_lower:
                return 3
            elif 'float' in dtype_lower or 'decimal' in dtype_lower:
                return 4
            elif 'datetime' in dtype_lower or 'timestamp' in dtype_lower or 'date' in dtype_lower:
                return 5
            else:
                return 6  # Other types last
        
        # Sort fields by dtype priority
        sorted_fields = sorted(schema.fields, key=lambda f: get_dtype_priority(f, df))
        
        # Display one line per column: column_name | value | Iceberg Type
        print(f"{'Column Name':<40} {'Value':<50} {'Iceberg Type':<25}")
        for field in sorted_fields:
            col_name = field.name
            field_type = str(field.field_type)
            
            # Get value from last record
            if col_name in last_record.index:
                value = last_record[col_name]
                formatted_value = format_value(value, max_len=48)
            else:
                formatted_value = "N/A (column not in data)"
            
            # Show: Column Name | Value | Iceberg Type (one line per column)
            print(f"{col_name:<40} {formatted_value:<50} {field_type:<25}")
        
        print(f"\nTotal columns: {len(schema.fields)}")
        print(f"Total rows in table: {len(df)}")
        
        print(f"\n{'='*80}\n")
        
    except Exception as e:
        print(f"\n❌ Error inspecting table: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Interactive script to inspect Iceberg tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
IMPORTANT: This script must be run inside the Docker container:
    docker-compose exec backend python3 app/scripts/inspect_table.py
        """
    )
    
    parser.add_argument(
        "--namespace",
        default="investflow",
        help="Namespace for tables (default: investflow)"
    )
    
    args = parser.parse_args()
    
    # Check if we have required environment variables
    if not os.getenv('LAKEKEEPER__BASE_URI'):
        print("\n" + "="*80)
        print("⚠️  WARNING: Environment variables not set!")
        print("="*80)
        print("\nThis script must be run inside the Docker container where")
        print("environment variables are configured.")
        print("\nTo run this script:")
        print("  cd /Users/matt/code/property/backend")
        print("  docker-compose exec backend python3 app/scripts/inspect_table.py")
        print("\n" + "="*80 + "\n")
        sys.exit(1)
    
    # Parse namespace
    namespace = tuple(args.namespace.split(".")) if "." in args.namespace else (args.namespace,)
    
    # Get available tables
    print("\n" + "="*80)
    print("Available Tables")
    print("="*80 + "\n")
    
    tables = get_available_tables(namespace)
    
    if not tables:
        print("No tables found.")
        sys.exit(1)
    
    # Display table list
    for i, table in enumerate(tables, 1):
        print(f"  {i:2d}. {table}")
    
    print(f"\n  {0:2d}. Exit")
    print("\n" + "="*80)
    
    # Interactive loop
    while True:
        try:
            choice = input(f"\nSelect table (1-{len(tables)}, 0 to exit): ").strip()
            
            if choice == "0":
                print("\nExiting...")
                break
            
            try:
                table_num = int(choice)
                if 1 <= table_num <= len(tables):
                    selected_table = tables[table_num - 1]
                    inspect_table(selected_table, namespace, limit=10)
                else:
                    print(f"❌ Invalid choice. Please enter a number between 1 and {len(tables)}")
            except ValueError:
                print("❌ Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
        
        except EOFError:
            print("\n\nExiting...")
            break
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break

if __name__ == "__main__":
    main()
