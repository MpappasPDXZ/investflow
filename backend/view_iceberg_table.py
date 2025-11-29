#!/usr/bin/env python3
"""
Interactive script to view data in Iceberg tables using PyIceberg
"""
import sys
import pandas as pd
from app.core.iceberg import get_catalog, read_table
from app.core.logging import get_logger

logger = get_logger(__name__)

def list_tables(namespace: tuple) -> list[str]:
    """List all tables in a namespace"""
    try:
        catalog = get_catalog()
        tables = catalog.list_tables(namespace)
        table_names = [t[-1] for t in tables]  # Extract table name (last element of tuple)
        return sorted(table_names)
    except Exception as e:
        logger.error(f"Failed to list tables: {e}", exc_info=True)
        return []

def view_table(namespace: str, table_name: str, limit: int = 100):
    """View data from an Iceberg table"""
    try:
        namespace_tuple = tuple(namespace.split("."))
        
        print(f"\n📊 Querying table: {namespace}.{table_name}")
        print("=" * 80)
        
        # Read table
        df = read_table(namespace_tuple, table_name, limit=limit)
        
        print(f"\n✅ Found {len(df)} rows")
        print(f"📋 Columns: {', '.join(df.columns.tolist())}")
        
        if len(df) > 0:
            print("\n" + "=" * 80)
            print("📄 Data:")
            print("=" * 80)
            
            # Convert to records for better formatting
            records = df.to_dict('records')
            
            # Print each row with better formatting
            for i, record in enumerate(records, 1):
                print(f"\n--- Row {i} ---")
                for key, value in record.items():
                    # Format the value for display
                    if pd.isna(value):
                        display_value = "NULL"
                    elif isinstance(value, (int, float)):
                        display_value = str(value)
                    elif isinstance(value, pd.Timestamp):
                        display_value = value.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        display_value = str(value)
                    
                    # Truncate long values
                    if len(display_value) > 60:
                        display_value = display_value[:57] + "..."
                    
                    print(f"  {key:30s}: {display_value}")
        else:
            print("\n⚠️  Table is empty")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Failed to view table: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Check for --list flag
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        # List tables mode
        namespace = sys.argv[2] if len(sys.argv) > 2 else "investflow"
        namespace_tuple = tuple(namespace.split("."))
        
        print(f"\n📋 Tables in namespace '{namespace}':")
        print("=" * 80)
        try:
            table_names = list_tables(namespace_tuple)
            if not table_names:
                print(f"⚠️  No tables found in namespace '{namespace}'")
            else:
                for i, table in enumerate(table_names, 1):
                    print(f"  {i}. {table}")
                print(f"\n✅ Total: {len(table_names)} table(s)")
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
        sys.exit(0)
    
    # Check if running in interactive mode (no args) or command-line mode
    if len(sys.argv) < 2:
        # Interactive mode
        print("\n" + "=" * 80)
        print("🔍 Iceberg Table Viewer - Interactive Mode")
        print("=" * 80)
        
        # Use default namespace
        namespace = "investflow"
        namespace_tuple = tuple(namespace.split("."))
        limit = 10  # Default limit
        
        # List available tables
        print(f"\n📋 Listing tables in namespace '{namespace}'...")
        try:
            table_names = list_tables(namespace_tuple)
            
            if not table_names:
                print(f"⚠️  No tables found in namespace '{namespace}'")
                sys.exit(0)
            
            print(f"\n✅ Found {len(table_names)} table(s):")
            print("-" * 80)
            for i, table in enumerate(table_names, 1):
                print(f"  {i}. {table}")
            print("-" * 80)
            
            # Get table selection
            while True:
                table_input = input(f"\n📊 Enter table name or number (1-{len(table_names)}): ").strip()
                
                # Check if it's a number
                if table_input.isdigit():
                    table_num = int(table_input)
                    if 1 <= table_num <= len(table_names):
                        table_name = table_names[table_num - 1]
                        break
                    else:
                        print(f"❌ Invalid number. Please enter 1-{len(table_names)}")
                        continue
                else:
                    # Check if it's a valid table name
                    if table_input in table_names:
                        table_name = table_input
                        break
                    else:
                        print(f"❌ Table '{table_input}' not found. Please try again.")
                        continue
            
            # View the table with default limit
            view_table(namespace, table_name, limit)
            
        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.error(f"Failed in interactive mode: {e}", exc_info=True)
            sys.exit(1)
    
    elif len(sys.argv) < 3:
        # Show usage
        print("Usage:")
        print("  Interactive mode: python view_iceberg_table.py")
        print("  List tables:      python view_iceberg_table.py --list [namespace]")
        print("  Command-line mode: python view_iceberg_table.py <namespace> <table_name> [limit]")
        print("\nExamples:")
        print("  python view_iceberg_table.py")
        print("  python view_iceberg_table.py --list")
        print("  python view_iceberg_table.py --list investflow")
        print("  python view_iceberg_table.py investflow properties 10")
        print("  python view_iceberg_table.py investflow expenses 50")
        sys.exit(1)
    else:
        # Command-line mode
        namespace = sys.argv[1]
        table_name = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        
        view_table(namespace, table_name, limit)

