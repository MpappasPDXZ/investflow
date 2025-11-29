"""
Generate vacancy expenses for all existing properties with square footage
"""
import sys
import asyncio
from pathlib import Path
from decimal import Decimal

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import read_table, table_exists
from app.core.logging import get_logger
from app.api.vacancy_utils import create_or_update_vacancy_expenses
import pandas as pd

NAMESPACE = ("investflow",)
TABLE_NAME = "properties"

logger = get_logger(__name__)


async def generate_all_vacancy_expenses():
    """
    Generate vacancy expenses for all properties that have square footage
    """
    logger.info("Generating vacancy expenses for existing properties...")
    
    try:
        # Check if properties table exists
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.warning("  ⚠️  Properties table doesn't exist yet")
            return
        
        # Read all properties
        df = read_table(NAMESPACE, TABLE_NAME)
        logger.info(f"  Found {len(df)} total properties")
        
        # Show what columns we have
        logger.info(f"  Columns: {df.columns.tolist()}")
        
        # Filter properties with square footage
        properties_with_sf = df[
            (df["square_feet"].notna()) & 
            (df["square_feet"] > 0) &
            (df["is_active"] == True)
        ]
        
        logger.info(f"  {len(properties_with_sf)} properties have square footage and are active")
        
        count = 0
        for _, row in properties_with_sf.iterrows():
            property_id = row["id"]
            square_feet = int(row["square_feet"])
            
            # Handle vacancy_rate - use default if None or NaN
            vacancy_val = row.get("vacancy_rate")
            if pd.isna(vacancy_val) or vacancy_val is None:
                vacancy_rate = Decimal("0.07")
            else:
                vacancy_rate = Decimal(str(vacancy_val))
            
            logger.info(f"  Processing property {property_id}: {square_feet} SF, {vacancy_rate*100}% vacancy")
            
            await create_or_update_vacancy_expenses(
                property_id=property_id,
                square_feet=square_feet,
                vacancy_rate=vacancy_rate
            )
            count += 1
        
        logger.info(f"  ✅ Generated vacancy expenses for {count} properties!")
        
    except Exception as e:
        logger.error(f"  ❌ Error generating vacancy expenses: {e}", exc_info=True)
        raise


def main():
    """Main function"""
    print("=" * 70)
    print("Generating Vacancy Expenses for Existing Properties")
    print("=" * 70)
    
    try:
        asyncio.run(generate_all_vacancy_expenses())
        print("\n✅ Vacancy expense generation completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

