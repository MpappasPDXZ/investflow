#!/usr/bin/env python3
"""
Script to check data in walkthroughs table
"""
import sys
from pathlib import Path
import pandas as pd

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, read_table

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
WALKTHROUGHS_TABLE = "walkthroughs"


def check_data():
    """Check data in walkthroughs table"""
    try:
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            logger.error(f"❌ Table {WALKTHROUGHS_TABLE} does not exist!")
            return False
        
        df = read_table(NAMESPACE, WALKTHROUGHS_TABLE)
        
        print("\n" + "=" * 80)
        print(f"DATA IN '{WALKTHROUGHS_TABLE}' TABLE")
        print("=" * 80)
        print(f"\nTotal walkthroughs: {len(df)}")
        print()
        
        if len(df) == 0:
            print("⚠️  No walkthroughs found in table")
            print()
            return True
        
        # Show column names
        print("COLUMNS IN DATA:")
        print("-" * 80)
        for i, col in enumerate(df.columns, 1):
            print(f"{i:2d}. {col}")
        print()
        
        # Show first few rows with key fields
        print("SAMPLE DATA (first 5 walkthroughs):")
        print("=" * 80)
        
        # Select key columns to display
        key_columns = [
            'id', 'property_display_name', 'unit_number', 'walkthrough_type', 
            'walkthrough_date', 'inspector_name', 'tenant_name', 'status'
        ]
        
        # Only show columns that exist
        display_columns = [col for col in key_columns if col in df.columns]
        
        if display_columns:
            display_df = df[display_columns].head(5)
            print(display_df.to_string(index=False))
        else:
            print(df.head(5).to_string(index=False))
        
        print()
        print("=" * 80)
        
        # Check for overall_condition in data
        if 'overall_condition' in df.columns:
            print("\n⚠️  WARNING: 'overall_condition' column still exists in data!")
        else:
            print("\n✅ 'overall_condition' column does NOT exist in data")
        
        print()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking data: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = check_data()
    sys.exit(0 if success else 1)

