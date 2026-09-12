#!/usr/bin/env python3
"""
Calculate tax depreciation for a specific property and user
"""
import sys
import os
from pathlib import Path
from decimal import Decimal
import pandas as pd

# Add app directory to path (when running from /app in Docker)
app_dir = Path(__file__).parent.parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))
    
# Also try adding parent directory (when running from backend/)
backend_dir = app_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, read_table
from app.api.tax_savings_utils import calculate_annual_depreciation
from app.services.auth_cache_service import auth_cache

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)

def main():
    property_address = "501 NE 67th Street"
    user_email = "matt.pappasemail@gmail.com"
    
    logger.info("=" * 80)
    logger.info(f"Calculating tax depreciation for:")
    logger.info(f"  Property: {property_address}")
    logger.info(f"  User: {user_email}")
    logger.info("=" * 80)
    
    # Get user by email
    user = auth_cache.get_user_by_email(user_email)
    if user is None:
        logger.error(f"❌ User not found: {user_email}")
        return
    
    user_id = user.get("id")
    tax_rate = Decimal(str(user.get("tax_rate", 0)))
    logger.info(f"✅ Found user: {user.get('email')}")
    logger.info(f"   User ID: {user_id}")
    logger.info(f"   Tax Rate: {tax_rate * 100}%")
    
    # Get property by address
    properties_df = read_table(NAMESPACE, "properties")
    if properties_df is None or properties_df.empty:
        logger.error("❌ Properties table is empty")
        return
    
    # Search for property by address (check both address_line1 and display_name)
    property_match = properties_df[
        (properties_df['address_line1'].str.contains(property_address, case=False, na=False)) |
        (properties_df['display_name'].str.contains(property_address, case=False, na=False))
    ]
    
    if property_match.empty:
        logger.error(f"❌ Property not found: {property_address}")
        logger.info("Available properties:")
        for idx, row in properties_df.iterrows():
            logger.info(f"  - {row.get('display_name', 'N/A')} | {row.get('address_line1', 'N/A')}")
        return
    
    property_row = property_match.iloc[0]
    property_id = property_row['id']
    current_market_value = property_row.get('current_market_value')
    purchase_date = property_row.get('purchase_date')
    display_name = property_row.get('display_name', 'N/A')
    address = property_row.get('address_line1', 'N/A')
    
    logger.info(f"✅ Found property: {display_name}")
    logger.info(f"   Property ID: {property_id}")
    logger.info(f"   Address: {address}")
    
    # Use current_market_value if available, otherwise fall back to purchase_price
    if pd.notna(current_market_value) and current_market_value is not None:
        property_value = Decimal(str(current_market_value))
        logger.info(f"   Current Market Value: ${property_value:,.2f} (used in calculation)")
    else:
        purchase_price = Decimal(str(property_row.get('purchase_price', 0)))
        property_value = purchase_price
        logger.info(f"   Current Market Value: Not set, using Purchase Price: ${property_value:,.2f}")
    
    if purchase_date:
        logger.info(f"   Purchase Date: {purchase_date} (not used in calculation)")
    
    # Verify property belongs to user
    property_user_id = str(property_row.get('user_id', ''))
    if property_user_id != user_id:
        logger.warning(f"⚠️  Property belongs to different user: {property_user_id}")
    
    # Calculate tax depreciation
    logger.info("")
    logger.info("=" * 80)
    logger.info("TAX DEPRECIATION CALCULATION:")
    logger.info("=" * 80)
    
    annual_amount = calculate_annual_depreciation(property_value, tax_rate)
    
    # Show breakdown
    depreciation_years = Decimal("27.5")
    annual_depreciation = property_value / depreciation_years
    annual_depreciation = annual_depreciation.quantize(Decimal('0.01'))
    
    logger.info("")
    logger.info("Formula: (Current Market Value ÷ 27.5 years) × Tax Rate")
    logger.info(f"Step 1: Annual Depreciation = ${property_value:,.2f} ÷ 27.5 = ${annual_depreciation:,.2f}/year")
    logger.info(f"Step 2: Tax Savings = ${annual_depreciation:,.2f} × {tax_rate * 100}% = ${annual_amount:,.2f}/year")
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"RESULT: Annual Tax Savings = ${annual_amount:,.2f}/year")
    logger.info("=" * 80)
    
    return annual_amount

if __name__ == "__main__":
    main()

