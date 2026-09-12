#!/usr/bin/env python3
"""
Check if the current user owns the property that has Ian Reeves expenses
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
        # Read properties table
        logger.info("Reading properties table...")
        properties_df = read_table(NAMESPACE, "properties")
        
        if properties_df is None or properties_df.empty:
            logger.warning("⚠️ Properties table is empty!")
            return
        
        # Read expenses table
        logger.info("Reading expenses table...")
        expenses_df = read_table(NAMESPACE, "expenses")
        
        # Find the property with Ian Reeves expenses
        ian_expenses = expenses_df[expenses_df['vendor'].str.contains('Ian', case=False, na=False)]
        if len(ian_expenses) == 0:
            logger.warning("⚠️ No Ian Reeves expenses found!")
            return
        
        # Get the property_id from Ian Reeves expenses
        property_id = ian_expenses.iloc[0]['property_id']
        logger.info(f"🔍 Ian Reeves expenses are for property_id: {property_id}")
        
        # Find this property in properties table
        property_row = properties_df[properties_df['id'].astype(str) == str(property_id)]
        
        if property_row.empty:
            logger.error(f"❌ Property {property_id} not found in properties table!")
            return
        
        property_user_id = property_row.iloc[0]['user_id']
        property_name = property_row.iloc[0].get('display_name', 'N/A')
        
        logger.info(f"✅ Property found:")
        logger.info(f"   Name: {property_name}")
        logger.info(f"   Property ID: {property_id}")
        logger.info(f"   User ID: {property_user_id}")
        logger.info(f"   Number of Ian Reeves expenses: {len(ian_expenses)}")
        
        # Show all users and their properties
        logger.info(f"\n📋 All users and their properties:")
        if 'user_id' in properties_df.columns and 'id' in properties_df.columns:
            for user_id in properties_df['user_id'].unique():
                user_props = properties_df[properties_df['user_id'] == user_id]
                logger.info(f"  User {user_id}: {len(user_props)} properties")
                for idx, prop in user_props.iterrows():
                    logger.info(f"    - {prop.get('id', 'N/A')}: {prop.get('display_name', 'N/A')}")
        
        logger.info(f"\n🔍 Summary:")
        logger.info(f"   Ian Reeves expenses belong to property: {property_name} (ID: {property_id})")
        logger.info(f"   This property belongs to user: {property_user_id}")
        logger.info(f"   If your current user_id doesn't match {property_user_id}, the expenses will be filtered out!")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()




