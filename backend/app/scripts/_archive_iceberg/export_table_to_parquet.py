#!/usr/bin/env python3
"""
Export Iceberg table data to local Parquet file.

IMPORTANT: This script must be run inside the Docker container:
    docker-compose exec backend python3 app/scripts/export_table_to_parquet.py

Usage:
    python export_table_to_parquet.py [--namespace NAMESPACE] [--output-dir DIR]
    
The script will:
1. Show a list of available tables
2. Let you select a table by number
3. Export all data to a local Parquet file
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

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

from app.core.iceberg import read_table, load_table
import pandas as pd

def get_available_tables(namespace: tuple = ("investflow",)):
    """Get list of available tables in the namespace"""
    # Known tables - we'll verify they exist
    known_tables = [
        "leases_full",
        "lease_tenants",
        "properties",
        "units",
        "tenants",
        "expenses",
        "rents",
        "walkthroughs",
        "documents",
        "comparables",
        "landlord_references"
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

def export_table_to_parquet(table_name: str, namespace: tuple = ("investflow",), output_dir: Path = None):
    """Export table data to Parquet file"""
    try:
        if output_dir is None:
            # Use /tmp (always writable in Docker containers)
            # Note: /app/app is mounted read-only in docker-compose, so we can't write there
            output_dir = Path("/tmp/iceberg_exports")
        else:
            output_dir = Path(output_dir)
        
        # Create output directory if it doesn't exist
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            # If we can't create the directory, try falling back to /tmp
            if output_dir != Path("/tmp/iceberg_exports"):
                print(f"\n⚠️  Warning: Cannot create output directory {output_dir}")
                print(f"   Error: {e}")
                print(f"   Falling back to /tmp/iceberg_exports (always writable in Docker)")
                output_dir = Path("/tmp/iceberg_exports")
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e2:
                    print(f"\n❌ Error: Cannot create fallback directory {output_dir}")
                    print(f"   Error: {e2}")
                    raise
            else:
                # If we're already trying /tmp and it fails, raise the error
                print(f"\n❌ Error: Cannot create output directory {output_dir}")
                print(f"   Error: {e}")
                print(f"\n   This is unexpected - /tmp should always be writable in Docker containers.")
                print(f"   Please check container permissions or specify a different directory using --output-dir")
                raise
        
        # Get absolute path for display
        abs_output_dir = output_dir.resolve()
        
        print(f"\n{'='*80}")
        print(f"Exporting table: {'.'.join(namespace)}.{table_name}")
        print(f"{'='*80}\n")
        
        # Load table to verify it exists
        table = load_table(namespace, table_name)
        schema = table.schema()
        
        print(f"Schema: {len(schema.fields)} columns")
        print("Reading all data from table...")
        
        # Read all data
        df = read_table(namespace, table_name)
        
        print(f"Total rows: {len(df)}")
        print(f"Total columns: {len(df.columns)}\n")
        
        if len(df) == 0:
            print("⚠️  Warning: Table is empty. Creating empty Parquet file anyway.")
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{table_name}_{timestamp}.parquet"
        filepath = output_dir / filename
        
        # Write to Parquet
        print(f"Writing to Parquet file...")
        df.to_parquet(filepath, index=False, engine='pyarrow')
        
        # Get file size
        file_size = filepath.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        # Get absolute path for display
        abs_filepath = filepath.resolve()
        
        print(f"\n{'='*80}")
        print("✅ Export completed successfully!")
        print(f"{'='*80}")
        print(f"File: {abs_filepath}")
        print(f"Relative: {filepath}")
        print(f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
        print(f"Rows: {len(df):,}")
        print(f"Columns: {len(df.columns)}")
        print(f"\nNote: File is saved in the Docker container at: {abs_filepath}")
        if str(abs_filepath).startswith("/tmp"):
            print(f"      To copy the file to your host machine, use:")
            print(f"      docker cp backend-local:{abs_filepath} ./")
        else:
            print(f"      File should be accessible from your host machine if the backend directory is mounted.")
        print(f"\n{'='*80}\n")
        
        return filepath
        
    except Exception as e:
        print(f"\n❌ Error exporting table: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Export Iceberg table data to local Parquet file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
IMPORTANT: This script must be run inside the Docker container:
    docker-compose exec backend python3 app/scripts/export_table_to_parquet.py
        """
    )
    
    parser.add_argument(
        "--namespace",
        default="investflow",
        help="Namespace for tables (default: investflow)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for Parquet files (default: /tmp/iceberg_exports). Note: /app/app is read-only in Docker, so use /tmp or another writable path."
    )
    
    parser.add_argument(
        "--table",
        type=str,
        default=None,
        help="Table name to export (if not provided, will show interactive menu)"
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
        print("  docker-compose exec backend python3 app/scripts/export_table_to_parquet.py")
        print("\n" + "="*80 + "\n")
        sys.exit(1)
    
    # Parse namespace
    namespace = tuple(args.namespace.split(".")) if "." in args.namespace else (args.namespace,)
    
    # Parse output directory
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    # If table name provided, export directly
    if args.table:
        export_table_to_parquet(args.table, namespace, output_dir)
        return
    
    # Otherwise, show interactive menu
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
            choice = input(f"\nSelect table to export (1-{len(tables)}, 0 to exit): ").strip()
            
            if choice == "0":
                print("\nExiting...")
                break
            
            try:
                table_num = int(choice)
                if 1 <= table_num <= len(tables):
                    selected_table = tables[table_num - 1]
                    export_table_to_parquet(selected_table, namespace, output_dir)
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

