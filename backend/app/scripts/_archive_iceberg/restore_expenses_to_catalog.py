#!/usr/bin/env python3
"""Restore recovered expense data back into Lakekeeper catalog"""
import asyncio
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
WAREHOUSE_NAME = settings.LAKEKEEPER__WAREHOUSE_NAME

async def main():
    logger.info("=== RESTORING YOUR EXPENSE DATA TO CATALOG ===")
    
    # Load recovered data
    df = pd.read_parquet('/app/app/RECOVERED_EXPENSES.parquet')
    logger.info(f"Loaded {len(df)} expense records")
    logger.info(f"Total amount: ${df['amount'].sum():,.2f}")
    
    # Initialize catalog
    catalog = RestCatalog(
        name="lakekeeper",
        uri=settings.LAKEKEEPER__BASE_URI + "/catalog",
        warehouse=WAREHOUSE_NAME,
        **{
            "credential": f"{settings.LAKEKEEPER__OAUTH2__CLIENT_ID}:{settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET}",
            "oauth2-server-uri": f"https://login.microsoftonline.com/{settings.LAKEKEEPER__OAUTH2__TENANT_ID}/oauth2/v2.0/token",
            "scope": settings.LAKEKEEPER__OAUTH2__SCOPE
        }
    )
    
    # Get the current expenses table
    table_name = f"{NAMESPACE[0]}.expenses"
    try:
        table = catalog.load_table(table_name)
        logger.info(f"Found existing expenses table")
        
        # Get current schema
        current_schema = table.schema()
        logger.info(f"Current schema fields: {[f.name for f in current_schema.fields]}")
        logger.info(f"Data columns: {df.columns.tolist()}")
        
        # Make sure required columns exist in dataframe, add if missing
        schema_fields = {f.name for f in current_schema.fields}
        for field in schema_fields:
            if field not in df.columns:
                logger.info(f"  Adding missing column '{field}' with null values")
                df[field] = None
        
        # Remove columns not in schema
        extra_cols = set(df.columns) - schema_fields
        if extra_cols:
            logger.info(f"  Removing extra columns: {extra_cols}")
            df = df.drop(columns=list(extra_cols))
        
        # Reorder to match schema
        df = df[[f.name for f in current_schema.fields if f.name in df.columns]]
        
        # Convert to PyArrow and append
        arrow_table = pa.Table.from_pandas(df, schema=current_schema.as_arrow())
        logger.info(f"Appending {len(df)} records to expenses table...")
        
        table.append(arrow_table)
        
        logger.info("✅ SUCCESS! Your expense data has been restored!")
        logger.info(f"Verifying... reading table data...")
        scan_result = table.scan().to_pandas()
        logger.info(f"Total records in table: {len(scan_result)}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.info("Data is saved in RECOVERED_EXPENSES.parquet")

if __name__ == "__main__":
    asyncio.run(main())

