"""
Migration script to create financial_performance table in Iceberg

Run this after deploying the new code:
    python backend/migrate_financial_performance.py
"""
import pyarrow as pa
from app.core.iceberg import get_catalog
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = "investflow"
TABLE_NAME = "financial_performance"


def create_financial_performance_table():
    """Create the financial_performance table if it doesn't exist"""
    try:
        catalog = get_catalog()
        
        # Check if table already exists
        try:
            existing_table = catalog.load_table(f"{NAMESPACE}.{TABLE_NAME}")
            logger.info(f"Table {NAMESPACE}.{TABLE_NAME} already exists")
            return
        except Exception:
            pass  # Table doesn't exist, continue
        
        # Define schema
        schema = pa.schema([
            pa.field("id", pa.string(), nullable=False),
            pa.field("property_id", pa.string(), nullable=False),
            pa.field("unit_id", pa.string(), nullable=True),
            pa.field("ytd_rent", pa.decimal128(19, 4), nullable=False),
            pa.field("ytd_expenses", pa.decimal128(19, 4), nullable=False),
            pa.field("ytd_profit_loss", pa.decimal128(19, 4), nullable=False),
            pa.field("cumulative_rent", pa.decimal128(19, 4), nullable=False),
            pa.field("cumulative_expenses", pa.decimal128(19, 4), nullable=False),
            pa.field("cumulative_profit_loss", pa.decimal128(19, 4), nullable=False),
            pa.field("current_market_value", pa.decimal128(19, 4), nullable=True),
            pa.field("purchase_price", pa.decimal128(19, 4), nullable=False),
            pa.field("cash_on_cash", pa.decimal128(19, 4), nullable=True),
            pa.field("last_calculated_at", pa.date32(), nullable=False),
            pa.field("created_at", pa.timestamp("us"), nullable=False),
            pa.field("updated_at", pa.timestamp("us"), nullable=False),
        ])
        
        # Create table
        table = catalog.create_table(
            identifier=f"{NAMESPACE}.{TABLE_NAME}",
            schema=schema
        )
        
        logger.info(f"✅ Successfully created table: {NAMESPACE}.{TABLE_NAME}")
        logger.info(f"Schema: {schema}")
        
    except Exception as e:
        logger.error(f"❌ Error creating financial_performance table: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    print("Creating financial_performance table...")
    create_financial_performance_table()
    print("✅ Migration complete!")

