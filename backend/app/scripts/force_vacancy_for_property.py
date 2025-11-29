"""
Force create vacancy expenses for a specific property
"""
import sys
import asyncio
from pathlib import Path
from decimal import Decimal

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import read_table, table_exists
from app.core.logging import get_logger
from app.api.vacancy_utils import create_or_update_vacancy_expenses
import pandas as pd

NAMESPACE = ("investflow",)
TABLE_NAME = "properties"
PROPERTY_ID = "00b1f6e9-174f-40a3-b2e9-af1518c6c69a"  # Your property ID

logger = get_logger(__name__)


async def force_create():
    """Force create vacancy expenses for the property"""
    try:
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error("Properties table doesn't exist")
            return
        
        df = read_table(NAMESPACE, TABLE_NAME)
        property_row = df[df["id"] == PROPERTY_ID]
        
        if property_row.empty:
            logger.error(f"Property {PROPERTY_ID} not found")
            return
        
        row = property_row.iloc[0]
        logger.info(f"Property data: {row.to_dict()}")
        
        square_feet = int(row["square_feet"]) if pd.notna(row.get("square_feet")) else None
        vacancy_val = row.get("vacancy_rate")
        vacancy_rate = Decimal(str(vacancy_val)) if pd.notna(vacancy_val) else Decimal("0.07")
        
        logger.info(f"Square Feet: {square_feet}")
        logger.info(f"Vacancy Rate: {vacancy_rate}")
        
        if not square_feet:
            logger.error("Property has no square footage!")
            return
        
        await create_or_update_vacancy_expenses(
            property_id=PROPERTY_ID,
            square_feet=square_feet,
            vacancy_rate=vacancy_rate
        )
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(force_create())

