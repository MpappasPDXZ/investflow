#!/usr/bin/env python3
"""
Restore rents data from backup parquet file
"""
import sys
import os
from pathlib import Path
import pandas as pd

# Add parent directory to path
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment
if not os.getenv('LAKEKEEPER__BASE_URI'):
    env_file = backend_dir / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

from app.core.iceberg import append_data

# Use the backup file from the first migration run
BACKUP_FILE = "/tmp/rents_backup_20260103_181226.parquet"
NAMESPACE = ("investflow",)

def main():
    print("=" * 80)
    print("Restore Rents Data from Backup")
    print("=" * 80)
    print()
    
    # Step 1: Load backup
    print(f"Step 1: Loading backup from {BACKUP_FILE}...")
    if not Path(BACKUP_FILE).exists():
        print(f"❌ Backup file not found: {BACKUP_FILE}")
        return
    
    df = pd.read_parquet(BACKUP_FILE)
    print(f"✅ Loaded {len(df)} rent payments from backup")
    print()
    
    # Step 2: Remove user_id and user_name columns
    print("Step 2: Removing user_id and user_name columns...")
    columns_to_drop = []
    if 'user_id' in df.columns:
        columns_to_drop.append('user_id')
    if 'user_name' in df.columns:
        columns_to_drop.append('user_name')
    
    if columns_to_drop:
        df = df.drop(columns=columns_to_drop)
        print(f"✅ Removed columns: {', '.join(columns_to_drop)}")
    else:
        print("✅ No user_id or user_name columns found")
    print()
    
    # Step 3: Upload to Iceberg
    print("Step 3: Uploading data to Iceberg...")
    append_data(NAMESPACE, "rents", df)
    print(f"✅ Successfully restored {len(df)} rent payments")
    print()
    
    print("=" * 80)
    print("✅ Restore completed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()

