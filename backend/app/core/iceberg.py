"""PyIceberg helper for direct Iceberg table operations"""
from typing import Optional, Tuple, List
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.table import Table
from pyiceberg.expressions import BooleanExpression, EqualTo
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global catalog instance
_catalog: Optional[Catalog] = None

def get_catalog() -> Catalog:
    """Get or create PyIceberg catalog"""
    global _catalog
    if _catalog is None:
        # Build OAuth2 config if available
        oauth_config = {}
        if settings.LAKEKEEPER__OAUTH2__CLIENT_ID and settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET:
            # Construct token endpoint from tenant_id if authority not set
            if settings.LAKEKEEPER__OAUTH2__AUTHORITY:
                token_endpoint = f"{settings.LAKEKEEPER__OAUTH2__AUTHORITY}/oauth2/v2.0/token"
            elif settings.LAKEKEEPER__OAUTH2__TENANT_ID:
                token_endpoint = f"https://login.microsoftonline.com/{settings.LAKEKEEPER__OAUTH2__TENANT_ID}/oauth2/v2.0/token"
            else:
                token_endpoint = None
            
            if token_endpoint:
                oauth_config = {
                    "credential": f"{settings.LAKEKEEPER__OAUTH2__CLIENT_ID}:{settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET}",
                    "oauth2-server-uri": token_endpoint,
                }
                if hasattr(settings, 'LAKEKEEPER__OAUTH2__SCOPE') and settings.LAKEKEEPER__OAUTH2__SCOPE:
                    oauth_config["scope"] = settings.LAKEKEEPER__OAUTH2__SCOPE
        
        _catalog = RestCatalog(
            name="lakekeeper",
            uri=settings.LAKEKEEPER__BASE_URI + "/catalog",
            warehouse=settings.LAKEKEEPER__WAREHOUSE_NAME,
            **oauth_config
        )
    return _catalog

def load_table(namespace: Tuple[str, ...], table_name: str) -> Table:
    """Load an Iceberg table"""
    catalog = get_catalog()
    table_identifier = (*namespace, table_name)
    return catalog.load_table(table_identifier)

def read_table(namespace: Tuple[str, ...], table_name: str, limit: Optional[int] = None) -> pd.DataFrame:
    """Read data from an Iceberg table"""
    try:
        table = load_table(namespace, table_name)
        scan = table.scan()
        arrow_table = scan.to_arrow()
        df = arrow_table.to_pandas()
        
        if limit:
            df = df.head(limit)
        
        return df
    except Exception as e:
        logger.error(f"Failed to read table {'.'.join((*namespace, table_name))}: {e}", exc_info=True)
        raise


def read_table_filtered(
    namespace: Tuple[str, ...], 
    table_name: str, 
    row_filter: BooleanExpression,
    selected_columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """Read filtered data from an Iceberg table using predicate pushdown.
    
    This is much faster than read_table() + pandas filtering because the filter
    is pushed down to the storage layer, avoiding full table scans.
    
    Args:
        namespace: Table namespace tuple
        table_name: Name of the table
        row_filter: PyIceberg filter expression (e.g., EqualTo("email", "user@example.com"))
        selected_columns: Optional list of columns to read (reduces I/O)
    
    Returns:
        Filtered DataFrame
    """
    try:
        table = load_table(namespace, table_name)
        # Only pass selected_fields if columns are specified (must be tuple)
        if selected_columns:
            scan = table.scan(row_filter=row_filter, selected_fields=tuple(selected_columns))
        else:
            scan = table.scan(row_filter=row_filter)
        arrow_table = scan.to_arrow()
        return arrow_table.to_pandas()
    except Exception as e:
        logger.error(f"Failed to read filtered table {'.'.join((*namespace, table_name))}: {e}", exc_info=True)
        raise

def append_data(namespace: Tuple[str, ...], table_name: str, data: pd.DataFrame):
    """Append data to an Iceberg table"""
    try:
        table = load_table(namespace, table_name)
        
        # Check if schema evolution is needed
        current_schema = table.schema()
        current_field_names = {field.name for field in current_schema.fields}
        data_columns = set(data.columns)
        missing_in_table = data_columns - current_field_names
        
        if missing_in_table:
            # Evolve schema to add missing columns
            logger.info(f"Evolving schema for {'.'.join((*namespace, table_name))} to add columns: {missing_in_table}")
            from pyiceberg.types import StringType, TimestampType, BooleanType
            
            # Use transaction to update schema
            with table.update_schema() as update:
                for col in missing_in_table:
                    # Check the actual type from the DataFrame
                    if data[col].dtype == 'object' or pd.api.types.is_string_dtype(data[col]):
                        field_type = StringType()
                    elif pd.api.types.is_datetime64_any_dtype(data[col]):
                        field_type = TimestampType()
                    elif pd.api.types.is_bool_dtype(data[col]):
                        field_type = BooleanType()
                    else:
                        # Default to string
                        field_type = StringType()
                    
                    # Add the column
                    update.add_column(col, field_type, required=False)
            
            # Reload table to get updated schema
            table = load_table(namespace, table_name)
            logger.info(f"Schema evolved successfully")
        
        # Convert timestamp columns from ns to us precision (Iceberg requirement)
        df = data.copy()
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype('datetime64[us]')
        
        # Convert numeric columns to Decimal if the schema expects it
        from decimal import Decimal as PythonDecimal
        from pyiceberg.types import DecimalType
        
        for field in current_schema.fields:
            if field.name in df.columns and isinstance(field.field_type, DecimalType):
                # Convert numeric values to Decimal
                df[field.name] = df[field.name].apply(
                    lambda x: PythonDecimal(str(x)) if pd.notna(x) and x is not None else None
                )
        
        # Reorder DataFrame columns to match table schema
        schema_column_order = [field.name for field in current_schema.fields]
        # Only include columns that exist in both the DataFrame and schema
        df = df[[col for col in schema_column_order if col in df.columns]]
        
        # Convert pandas DataFrame to PyArrow table without schema first
        arrow_table = pa.Table.from_pandas(df)
        
        # Cast to the table's schema - this handles type conversions properly
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        
        table.append(arrow_table)
    except Exception as e:
        # If table doesn't exist, provide helpful error
        error_str = str(e).lower()
        if "does not exist" in error_str or "not found" in error_str:
            logger.error(f"Table {'.'.join((*namespace, table_name))} does not exist. Please create it first using create_data.py script.")
            raise ValueError(f"Table {'.'.join((*namespace, table_name))} does not exist. Please run the create_data.py script to create tables.")
        logger.error(f"Failed to append data to {'.'.join((*namespace, table_name))}: {e}", exc_info=True)
        raise

def evolve_schema_if_needed(namespace: Tuple[str, ...], table_name: str, required_columns: list[str]):
    """Evolve table schema to add missing columns if needed"""
    try:
        table = load_table(namespace, table_name)
        current_schema = table.schema()
        current_field_names = {field.name for field in current_schema.fields}
        
        # Check if any required columns are missing
        missing_columns = [col for col in required_columns if col not in current_field_names]
        
        if missing_columns:
            logger.info(f"Evolving schema for {'.'.join((*namespace, table_name))} to add columns: {missing_columns}")
            # For now, we'll let union_by_name handle it, but in the future we could add schema evolution here
            # This is a placeholder - actual schema evolution would require more complex logic
            pass
    except Exception as e:
        logger.warning(f"Could not check/evolve schema for {'.'.join((*namespace, table_name))}: {e}")

def table_exists(namespace: Tuple[str, ...], table_name: str) -> bool:
    """Check if a table exists"""
    try:
        load_table(namespace, table_name)
        return True
    except Exception:
        return False

