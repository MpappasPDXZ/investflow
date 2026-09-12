#!/usr/bin/env python3
"""
Inspect expenses table to debug missing expenses issue
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog
import pandas as pd

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "expenses"

def main():
    catalog = get_catalog()
    
    try:
        # Load expenses table
        logger.info(f"Loading table: {NAMESPACE}.{TABLE_NAME}")
        table = catalog.load_table(f"{'.'.join(NAMESPACE)}.{TABLE_NAME}")
        
        # Read all expenses
        logger.info("Reading all expenses...")
        scan = table.scan()
        arrow_table = scan.to_arrow()
        df = pd.DataFrame(arrow_table.to_pylist())
        
        if df.empty:
            logger.warning("⚠️ Expenses table is EMPTY!")
            return
        
        logger.info(f"✅ Found {len(df)} total expenses in table")
        
        # Show all columns
        logger.info(f"\n📊 Columns in expenses table: {list(df.columns)}")
        
        # Check for Ian Reeves expenses
        logger.info("\n🔍 Searching for expenses with 'Ian' in vendor...")
        if 'vendor' in df.columns:
            ian_expenses = df[df['vendor'].str.contains('Ian', case=False, na=False)]
            logger.info(f"Found {len(ian_expenses)} expenses with 'Ian' in vendor")
            
            if len(ian_expenses) > 0:
                logger.info("\n📋 Ian Reeves expenses:")
                for idx, row in ian_expenses.iterrows():
                    logger.info(f"  - ID: {row.get('id', 'N/A')}")
                    logger.info(f"    Property ID: {row.get('property_id', 'N/A')}")
                    logger.info(f"    Vendor: {row.get('vendor', 'N/A')}")
                    logger.info(f"    Description: {row.get('description', 'N/A')}")
                    logger.info(f"    Amount: {row.get('amount', 'N/A')}")
                    logger.info(f"    Date: {row.get('date', 'N/A')}")
                    logger.info(f"    Expense Type: {row.get('expense_type', 'N/A')}")
                    logger.info("")
            else:
                logger.warning("⚠️ No expenses found with 'Ian' in vendor")
        else:
            logger.warning("⚠️ 'vendor' column not found in expenses table")
        
        # Check property_ids
        logger.info("\n🔍 Checking property_id distribution...")
        if 'property_id' in df.columns:
            property_counts = df['property_id'].value_counts()
            logger.info(f"Expenses by property_id:")
            for prop_id, count in property_counts.items():
                logger.info(f"  {prop_id}: {count} expenses")
        
        # Check for expenses with null property_id
        if 'property_id' in df.columns:
            null_property = df[df['property_id'].isna()]
            logger.info(f"\n⚠️ Found {len(null_property)} expenses with NULL property_id")
            if len(null_property) > 0:
                logger.info("These expenses will be filtered out by the API!")
        
        # Check all vendors
        logger.info("\n🔍 All unique vendors:")
        if 'vendor' in df.columns:
            vendors = df['vendor'].dropna().unique()
            for vendor in sorted(vendors):
                count = len(df[df['vendor'] == vendor])
                logger.info(f"  {vendor}: {count} expenses")
        
        # Show sample of all expenses
        logger.info("\n📋 Sample of first 10 expenses:")
        for idx, row in df.head(10).iterrows():
            logger.info(f"  - {row.get('vendor', 'N/A')} | {row.get('description', 'N/A')[:50]} | Property: {row.get('property_id', 'N/A')} | Date: {row.get('date', 'N/A')}")
        
        # Now check properties table to see which properties belong to which users
        logger.info("\n🔍 Checking properties table for user ownership...")
        try:
            properties_table = catalog.load_table(f"{'.'.join(NAMESPACE)}.properties")
            props_scan = properties_table.scan()
            props_arrow = props_scan.to_arrow()
            props_df = pd.DataFrame(props_arrow.to_pylist())
            
            logger.info(f"Found {len(props_df)} properties")
            
            if 'user_id' in props_df.columns and 'id' in props_df.columns:
                logger.info("\nProperties by user_id:")
                user_props = props_df.groupby('user_id')['id'].apply(list).to_dict()
                for user_id, prop_ids in user_props.items():
                    logger.info(f"  User {user_id}: {len(prop_ids)} properties")
                    logger.info(f"    Property IDs: {prop_ids}")
                
                # Check if expense property_ids match any user's properties
                if 'property_id' in df.columns:
                    all_property_ids = set(props_df['id'].astype(str))
                    expense_property_ids = set(df['property_id'].dropna().astype(str))
                    
                    logger.info(f"\n🔍 Property ID matching:")
                    logger.info(f"  Properties in properties table: {len(all_property_ids)}")
                    logger.info(f"  Property IDs in expenses: {len(expense_property_ids)}")
                    
                    missing_properties = expense_property_ids - all_property_ids
                    if missing_properties:
                        logger.warning(f"⚠️ Found {len(missing_properties)} expense property_ids that don't exist in properties table:")
                        for prop_id in missing_properties:
                            logger.warning(f"    {prop_id}")
                            expenses_with_missing = df[df['property_id'].astype(str) == prop_id]
                            logger.warning(f"      {len(expenses_with_missing)} expenses with this property_id")
        except Exception as e:
            logger.error(f"Error checking properties table: {e}", exc_info=True)
        
    except Exception as e:
        logger.error(f"Error inspecting expenses: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()




