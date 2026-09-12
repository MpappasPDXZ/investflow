#!/usr/bin/env python3
"""
Check if expenses have property_ids that don't match properties table
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, read_table
import pandas as pd

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)

def main():
    catalog = get_catalog()
    
    try:
        # Read expenses table
        logger.info("Reading expenses table...")
        expenses_df = read_table(NAMESPACE, "expenses")
        
        if expenses_df is None or expenses_df.empty:
            logger.warning("⚠️ Expenses table is empty!")
            return
        
        logger.info(f"✅ Found {len(expenses_df)} expenses")
        
        # Read properties table
        logger.info("Reading properties table...")
        properties_df = read_table(NAMESPACE, "properties")
        
        if properties_df is None or properties_df.empty:
            logger.warning("⚠️ Properties table is empty!")
            return
        
        logger.info(f"✅ Found {len(properties_df)} properties")
        
        # Get all property IDs from properties table
        if 'id' not in properties_df.columns:
            logger.error("❌ Properties table doesn't have 'id' column!")
            return
        
        valid_property_ids = set(properties_df['id'].astype(str))
        logger.info(f"✅ Found {len(valid_property_ids)} unique property IDs in properties table")
        
        # Check expenses property_ids
        if 'property_id' not in expenses_df.columns:
            logger.error("❌ Expenses table doesn't have 'property_id' column!")
            return
        
        # Get unique property_ids from expenses
        expense_property_ids = set(expenses_df['property_id'].dropna().astype(str))
        logger.info(f"✅ Found {len(expense_property_ids)} unique property IDs in expenses table")
        
        # Find mismatches
        missing_property_ids = expense_property_ids - valid_property_ids
        logger.info(f"\n🔍 Checking for mismatches...")
        
        if missing_property_ids:
            logger.warning(f"❌ Found {len(missing_property_ids)} expense property_ids that DON'T exist in properties table:")
            for prop_id in missing_property_ids:
                expenses_with_this_id = expenses_df[expenses_df['property_id'].astype(str) == prop_id]
                logger.warning(f"  Property ID: {prop_id}")
                logger.warning(f"    {len(expenses_with_this_id)} expenses with this property_id")
                logger.warning(f"    Vendors: {expenses_with_this_id['vendor'].dropna().unique().tolist()}")
                logger.warning(f"    Descriptions: {expenses_with_this_id['description'].head(3).tolist()}")
        else:
            logger.info("✅ All expense property_ids exist in properties table!")
        
        # Check for expenses with null property_id
        null_property_expenses = expenses_df[expenses_df['property_id'].isna()]
        if len(null_property_expenses) > 0:
            logger.warning(f"\n⚠️ Found {len(null_property_expenses)} expenses with NULL property_id")
            logger.warning("These will be filtered out by the API!")
        
        # Show sample of properties
        logger.info(f"\n📋 Sample of properties (first 5):")
        for idx, row in properties_df.head(5).iterrows():
            logger.info(f"  ID: {row.get('id', 'N/A')} | Name: {row.get('display_name', 'N/A')} | User: {row.get('user_id', 'N/A')}")
        
        # Show expenses with Ian
        logger.info(f"\n🔍 Expenses with 'Ian' in vendor:")
        ian_expenses = expenses_df[expenses_df['vendor'].str.contains('Ian', case=False, na=False)]
        if len(ian_expenses) > 0:
            for idx, row in ian_expenses.iterrows():
                prop_id = row.get('property_id', 'NULL')
                is_valid = str(prop_id) in valid_property_ids if pd.notna(prop_id) else False
                status = "✅ VALID" if is_valid else "❌ INVALID"
                logger.info(f"  {status} | Property ID: {prop_id} | Vendor: {row.get('vendor', 'N/A')} | Description: {row.get('description', 'N/A')[:50]}")
        else:
            logger.warning("⚠️ No expenses found with 'Ian' in vendor")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()




