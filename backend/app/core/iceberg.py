"""PyIceberg helper for direct Iceberg table operations"""
from typing import Optional, Tuple, List
from datetime import datetime, date
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

# USAGE: get_catalog() is used in:
# - app/api/walkthroughs.py
# - app/api/leases.py
# - app/api/comparables.py
# - app/api/properties.py
# - app/api/scheduled.py
# - app/services/financial_performance_service.py
# - app/services/expense_service.py
# - app/services/document_service.py
# - app/scripts/recreate_leases_table.py
# - app/scripts/migrate_walkthroughs_remove_fields.py
# - app/scripts/migrate_pets_to_json_column.py
# - app/scripts/migrate_leases_merge_tenants.py
# - app/scripts/rename_leases_to_comps.py
# - app/scripts/migrate_leases_full_fix_schema.py
# - app/scripts/migrate_rents_remove_user_columns.py
# - app/scripts/migrate_tenants_remove_columns.py
# - app/scripts/migrate_expenses_add_has_receipt.py
# - app/scripts/migrate_expenses_remove_columns.py
# - app/scripts/migrate_fix_file_size_type.py
# - app/scripts/migrate_fix_properties_column_types.py
# - app/scripts/migrate_add_fields.py
# - app/scripts/add_rental_history_fields.py
# - app/scripts/migrate_rents_add_columns.py
# - app/scripts/remove_overall_condition_from_walkthroughs.py
# - app/scripts/check_walkthroughs_columns.py
# - app/scripts/add_property_unit_text_to_walkthroughs.py
# - app/scripts/migrate_areas_to_json.py
# - app/scripts/add_areas_json_to_walkthroughs.py
# - app/scripts/migrate_walkthrough_inspection_status.py
# - app/scripts/migrate_leases_clean_schema.py
# - app/scripts/verify_lease_schema.py
# - app/scripts/remove_old_landlord_fields.py
# - app/scripts/recreate_leases_full.py
# - app/scripts/migrate_lease_utilities_doors.py
# - app/scripts/migrate_leases_add_date_rented.py
# - app/scripts/add_maintenance_fields.py
# - app/scripts/add_holding_fee_fields.py
# - app/scripts/add_lease_fields_v2.py
# - app/scripts/remove_eviction_fields.py
# - app/scripts/add_tenant_id_to_documents.py
# - app/scripts/upload_316_lease.py
# - app/scripts/restore_scheduled_data.py
# - app/scripts/restore_all_data.py
# - app/main.py
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

# USAGE: load_table() is used in:
# - app/api/walkthroughs.py
# - app/api/leases.py
# - app/api/comparables.py
# - app/api/properties.py
# - app/api/tax_savings_utils.py
# - app/api/tenants.py
# - app/services/expense_service.py
# - app/services/document_service.py
# - app/scripts/analyze_frontend_changes.py
# - app/scripts/generate_lease_column_mapping.py
# - app/scripts/recreate_leases_table.py
# - app/scripts/check_lease_table_columns.py
# - app/scripts/restore_leases_table.py
# - app/scripts/migrate_walkthroughs_remove_fields.py
# - app/scripts/migrate_pets_to_json_column.py
# - app/scripts/migrate_leases_merge_tenants.py
# - app/scripts/rename_leases_to_comps.py
# - app/scripts/inspect_table.py
# - app/scripts/migrate_leases_full_fix_schema.py
# - app/scripts/update_document_type_background_check.py
# - app/services/financial_performance_service.py
# - app/scripts/normalize_document_storage_id.py
# - app/scripts/migrate_expenses_remove_columns.py
# - app/scripts/migrate_fix_file_size_type.py
# - app/scripts/inspect_expenses.py
# - app/scripts/create_data.py
# - app/scripts/migrate_fix_properties_column_types.py
# - app/scripts/export_table_to_parquet.py
# - app/scripts/migrate_add_fields.py
# - app/scripts/add_rental_history_fields.py
# - app/scripts/remove_overall_condition_from_walkthroughs.py
# - app/scripts/check_walkthroughs_columns.py
# - app/scripts/add_property_unit_text_to_walkthroughs.py
# - app/scripts/add_areas_json_to_walkthroughs.py
# - app/scripts/migrate_leases_clean_schema.py
# - app/scripts/generate_lease_column_mapping_detailed.py
# - app/scripts/verify_lease_schema.py
# - app/scripts/remove_old_landlord_fields.py
# - app/scripts/recreate_leases_full.py
# - app/scripts/migrate_lease_utilities_doors.py
# - app/scripts/migrate_leases_add_date_rented.py
# - app/api/landlord_references.py
# - app/scripts/add_maintenance_fields.py
# - app/scripts/add_holding_fee_fields.py
# - app/scripts/add_lease_fields_v2.py
# - app/scripts/remove_eviction_fields.py
# - app/scripts/add_tenant_id_to_documents.py
# - app/scripts/upload_316_lease.py
# - app/scripts/restore_scheduled_data.py
# - app/scripts/restore_expenses_to_catalog.py
# - app/scripts/restore_all_data.py
# - app/api/users.py
# - app/api/shares.py
# - app/api/vacancy_utils.py
def load_table(namespace: Tuple[str, ...], table_name: str) -> Table:
    """Load an Iceberg table"""
    catalog = get_catalog()
    table_identifier = (*namespace, table_name)
    return catalog.load_table(table_identifier)

# USAGE: read_table() is used in:
# - app/api/walkthroughs.py
# - app/api/leases.py
# - app/api/comparables.py
# - app/api/properties.py
# - app/api/tax_savings_utils.py
# - app/api/scheduled.py
# - app/api/tenants.py
# - app/services/financial_performance_service.py
# - app/services/financial_performance_cache_service.py
# - app/scripts/check_lease_table_columns.py
# - app/scripts/restore_leases_table.py
# - app/scripts/migrate_walkthroughs_remove_fields.py
# - app/scripts/migrate_pets_to_json_column.py
# - app/scripts/migrate_leases_merge_tenants.py
# - app/scripts/rename_leases_to_comps.py
# - app/scripts/inspect_table.py
# - app/scripts/migrate_leases_full_fix_schema.py
# - app/scripts/calculate_tax_depreciation.py
# - app/scripts/recalculate_tax_savings.py
# - app/scripts/update_document_type_background_check.py
# - app/scripts/migrate_rents_remove_user_columns.py
# - app/scripts/backfill_has_receipt.py
# - app/api/rent.py
# - app/scripts/backfill_document_property_id.py
# - app/scripts/migrate_tenants_remove_columns.py
# - app/scripts/migrate_expenses_add_has_receipt.py
# - app/scripts/migrate_expenses_remove_columns.py
# - app/scripts/migrate_fix_file_size_type.py
# - app/scripts/check_expense_property_mismatch.py
# - app/scripts/check_user_property_mismatch.py
# - app/scripts/create_data.py
# - app/scripts/migrate_fix_properties_column_types.py
# - app/scripts/export_table_to_parquet.py
# - app/validate_lease_fields.py
# - app/scripts/migrate_rents_add_columns.py
# - app/scripts/check_walkthroughs_data.py
# - app/scripts/remove_overall_condition_from_walkthroughs.py
# - app/scripts/add_property_unit_text_to_walkthroughs.py
# - app/scripts/migrate_areas_to_json.py
# - app/scripts/migrate_walkthrough_inspection_status.py
# - app/scripts/generate_lease_column_mapping_detailed.py
# - app/scripts/backup_leases_4_active.py
# - app/scripts/backup_leases_table.py
# - app/scripts/check_lease_data.py
# - app/scripts/recreate_leases_full.py
# - app/api/landlord_references.py
# - app/api/units.py
# - app/api/financial_performance.py
# - app/services/scheduled_financials_template_service.py
# - app/api/scheduled_template.py
# - app/api/users.py
# - app/services/auth_cache_service.py
# - app/api/shares.py
# - app/api/vacancy_utils.py
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

# USAGE: read_table_filtered() is used in:
# - app/api/walkthroughs.py
# - app/api/leases.py
# - app/api/properties.py
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

# USAGE: append_data() is used in:
# - app/api/leases.py
# - app/api/tax_savings_utils.py
# - app/services/expense_service.py
# - app/api/tenants.py
# - app/services/document_service.py
# - app/api/rent.py
# - app/scripts/restore_leases_table.py
# - app/scripts/migrate_walkthroughs_remove_fields.py
# - app/scripts/migrate_pets_to_json_column.py
# - app/scripts/migrate_rents_remove_user_columns.py
# - app/scripts/migrate_tenants_remove_columns.py
# - app/scripts/migrate_expenses_add_has_receipt.py
# - app/scripts/normalize_document_storage_id.py
# - app/scripts/migrate_expenses_remove_columns.py
# - app/scripts/create_data.py
# - app/scripts/migrate_rents_add_columns.py
# - app/scripts/restore_rents_from_backup.py
# - app/scripts/remove_overall_condition_from_walkthroughs.py
# - app/scripts/add_property_unit_text_to_walkthroughs.py
# - app/scripts/migrate_areas_to_json.py
# - app/scripts/migrate_leases_clean_schema.py
# - app/scripts/recreate_leases_full.py
# - app/api/landlord_references.py
# - app/api/units.py
# - app/api/scheduled_template.py
# - app/api/auth.py
# - app/api/users.py
# - app/api/shares.py
# - app/api/vacancy_utils.py
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
        
        # Convert date columns to date32 if schema expects it
        from pyiceberg.types import DateType
        for field in current_schema.fields:
            if field.name in df.columns and isinstance(field.field_type, DateType):
                # Convert date/datetime to date (date32)
                if pd.api.types.is_datetime64_any_dtype(df[field.name]):
                    df[field.name] = pd.to_datetime(df[field.name]).dt.date
                elif df[field.name].dtype == 'object':
                    # Try to parse as date
                    df[field.name] = pd.to_datetime(df[field.name], errors='coerce').dt.date
        
        # Convert date columns to date32 if schema expects it
        from pyiceberg.types import DateType
        for field in current_schema.fields:
            if field.name in df.columns and isinstance(field.field_type, DateType):
                # Convert date/datetime to date (date32)
                if pd.api.types.is_datetime64_any_dtype(df[field.name]):
                    df[field.name] = pd.to_datetime(df[field.name]).dt.date
                elif df[field.name].dtype == 'object':
                    # Try to parse as date
                    df[field.name] = pd.to_datetime(df[field.name], errors='coerce').dt.date
        
                # Convert numeric columns to Decimal if the schema expects it
        from decimal import Decimal as PythonDecimal
        from pyiceberg.types import DecimalType
        
        for field in current_schema.fields:
            if field.name in df.columns and isinstance(field.field_type, DecimalType):
                # Get precision from schema
                precision = field.field_type.precision
                scale = field.field_type.scale
                
                # Round to the scale (decimal places) to prevent data loss
                # Convert all values to Decimal, handling various numeric types
                def to_decimal(x):
                    if pd.isna(x) or x is None:
                        return None
                    # Handle string, int, float, or Decimal
                    try:
                        if isinstance(x, PythonDecimal):
                            return PythonDecimal(str(round(float(x), scale)))
                        else:
                            return PythonDecimal(str(round(float(x), scale)))
                    except (ValueError, TypeError):
                        return None
                
                df[field.name] = df[field.name].apply(to_decimal)
        
        # Convert integer columns to proper types
        from pyiceberg.types import IntegerType, LongType
        
        for field in current_schema.fields:
            if field.name not in df.columns:
                continue
            
            # Handle Integer types - convert floats/doubles to ints
            if isinstance(field.field_type, (IntegerType, LongType)):
                def to_int(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return int(x)
                    except (ValueError, TypeError):
                        return None
                
                df[field.name] = df[field.name].apply(to_int)
        
        # Reorder DataFrame columns to match table schema and add missing columns
        schema_column_order = [field.name for field in current_schema.fields]
        schema_field_names = set(schema_column_order)
        
        # Add missing columns with None values
        for col in schema_column_order:
            if col not in df.columns:
                df[col] = None
        
        # Only include columns that exist in the schema (remove any extra columns)
        columns_to_remove = [col for col in df.columns if col not in schema_field_names]
        if columns_to_remove:
            logger.warning(f"Removing columns from DataFrame that don't exist in table schema: {columns_to_remove}")
            df = df.drop(columns=columns_to_remove)
        
        # Reorder to match schema order
        df = df[schema_column_order]
        
        # Convert timestamp columns from nanoseconds to microseconds (Iceberg requirement)
        # Pandas defaults to timestamp[ns] but Iceberg only supports timestamp[us]
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                # Convert to datetime64[us] (microseconds) instead of datetime64[ns] (nanoseconds)
                df[col] = df[col].astype('datetime64[us]')
        
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

# USAGE: evolve_schema_if_needed() is NOT currently used anywhere in the codebase
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

# USAGE: table_exists() is used in:
# - app/api/walkthroughs.py
# - app/api/leases.py
# - app/api/comparables.py
# - app/api/properties.py
# - app/api/tax_savings_utils.py
# - app/services/financial_performance_service.py
# - app/scripts/recreate_leases_table.py
# - app/scripts/restore_leases_table.py
# - app/scripts/migrate_walkthroughs_remove_fields.py
# - app/scripts/migrate_pets_to_json_column.py
# - app/scripts/migrate_leases_merge_tenants.py
# - app/scripts/rename_leases_to_comps.py
# - app/scripts/migrate_leases_full_fix_schema.py
# - app/scripts/migrate_rents_remove_user_columns.py
# - app/scripts/backfill_has_receipt.py
# - app/scripts/migrate_tenants_remove_columns.py
# - app/scripts/migrate_expenses_add_has_receipt.py
# - app/services/financial_performance_cache_service.py
# - app/scripts/migrate_expenses_remove_columns.py
# - app/scripts/migrate_fix_file_size_type.py
# - app/scripts/migrate_fix_properties_column_types.py
# - app/scripts/migrate_add_fields.py
# - app/scripts/migrate_rents_add_columns.py
# - app/scripts/check_walkthroughs_data.py
# - app/scripts/remove_overall_condition_from_walkthroughs.py
# - app/scripts/check_walkthroughs_columns.py
# - app/scripts/add_property_unit_text_to_walkthroughs.py
# - app/scripts/migrate_areas_to_json.py
# - app/scripts/add_areas_json_to_walkthroughs.py
# - app/scripts/migrate_walkthrough_inspection_status.py
# - app/scripts/backup_leases_table.py
# - app/scripts/verify_lease_schema.py
# - app/scripts/recreate_leases_full.py
# - app/scripts/migrate_lease_utilities_doors.py
# - app/scripts/migrate_leases_add_date_rented.py
# - app/api/landlord_references.py
# - app/api/units.py
# - app/api/financial_performance.py
# - app/services/scheduled_financials_template_service.py
# - app/api/users.py
# - app/services/auth_cache_service.py
# - app/api/shares.py
# - app/api/vacancy_utils.py
def table_exists(namespace: Tuple[str, ...], table_name: str) -> bool:
    """Check if a table exists"""
    try:
        load_table(namespace, table_name)
        return True
    except Exception:
        return False

# USAGE: upsert_data() is used in:
# - app/api/leases.py
# - app/api/comparables.py
# - app/api/landlord_references.py
# - app/api/units.py
def upsert_data(namespace: Tuple[str, ...], table_name: str, data: pd.DataFrame, join_cols: list[str] = None):
    """
    Upsert data to an Iceberg table using the same conversion logic as append_data.
    
    Args:
        namespace: Table namespace tuple
        table_name: Name of the table
        data: DataFrame to upsert
        join_cols: Columns to use for join (default: ["id"])
    """
    import time
    start_time = time.time()
    
    if join_cols is None:
        join_cols = ["id"]
        
    try:
        step_start = time.time()
        table = load_table(namespace, table_name)
        current_schema = table.schema()
        logger.info(f"[PERF] upsert_data: load_table took {time.time() - step_start:.3f}s")
        
        # CRITICAL FIX: Convert timestamp columns IMMEDIATELY after copying the DataFrame
        # Pandas creates timestamp[ns] by default, but Iceberg only supports timestamp[us]
        df = data.copy()
        
        # Get schema first to know which columns are timestamps vs dates
        table_schema = table.schema().as_arrow()
        schema_field_types = {field.name: field.type for field in table_schema}
        
        # Convert all datetime columns based on their schema type BEFORE any other operations
        for col in df.columns:
            if col in schema_field_types:
                field_type = schema_field_types[col]
                # If schema expects a timestamp, convert ns to us
                if pa.types.is_timestamp(field_type):
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        logger.info(f"Converting timestamp column {col} from ns to us")
                        df[col] = df[col].astype('datetime64[us]')
                # If schema expects a date, convert to date objects
                elif pa.types.is_date(field_type):
                    logger.info(f"Converting date column {col} - current dtype: {df[col].dtype}")
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        logger.info(f"  Column {col} is datetime64, converting to date objects")
                        df[col] = pd.to_datetime(df[col]).dt.date
                    # Ensure column stays as object dtype with date values
                    # Force conversion even if already looks like dates
                    if df[col].dtype != object:
                        logger.info(f"  Forcing {col} to object dtype")
                        df[col] = df[col].astype(object)
                    logger.info(f"  Final dtype for {col}: {df[col].dtype}, sample value: {df[col].iloc[0] if len(df) > 0 and pd.notna(df[col].iloc[0]) else 'None'}")
        
        # Remove old conversion logic - now handled above
        # Convert date columns to date32 if schema expects it
        from pyiceberg.types import DateType
        for field in current_schema.fields:
            if field.name in df.columns and isinstance(field.field_type, DateType):
                # Convert date/datetime to date (date32)
                if pd.api.types.is_datetime64_any_dtype(df[field.name]):
                    df[field.name] = pd.to_datetime(df[field.name]).dt.date
                elif df[field.name].dtype == 'object':
                    # Try to parse as date
                    df[field.name] = pd.to_datetime(df[field.name], errors='coerce').dt.date
        
        # Convert numeric columns to proper types based on schema
        from decimal import Decimal as PythonDecimal
        from pyiceberg.types import DecimalType, IntegerType, LongType
        
        for field in current_schema.fields:
            if field.name not in df.columns:
                continue
                
            # Handle Decimal types
            if isinstance(field.field_type, DecimalType):
                scale = field.field_type.scale
                
                def to_decimal(x, s=scale):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return PythonDecimal(str(round(float(x), s)))
                    except (ValueError, TypeError):
                        return None
                
                df[field.name] = df[field.name].apply(to_decimal)
            
            # Handle Integer types - convert floats/doubles to ints
            elif isinstance(field.field_type, (IntegerType, LongType)):
                def to_int(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return int(x)
                    except (ValueError, TypeError):
                        return None
                
                df[field.name] = df[field.name].apply(to_int)
        logger.info(f"[PERF] upsert_data: Type conversions took {time.time() - step_start:.3f}s")
        
        # CRITICAL: PyIceberg's upsert compares DataFrame schema with existing parquet file schemas
        # If schema evolution added new columns, existing parquet files won't have them
        # We need to determine which columns exist in the actual data files
        
        # Read existing row to get actual parquet file schema
        step_start = time.time()
        join_col = join_cols[0] if join_cols else "id"
        join_value = df[join_col].iloc[0] if len(df) > 0 else None
        
        existing_columns = set()
        if join_value is not None:
            try:
                existing_data = table.scan(
                    row_filter=f"{join_col} == '{join_value}'"
                ).to_pandas()
                if not existing_data.empty:
                    existing_columns = set(existing_data.columns)
                    logger.info(f"Existing row has columns: {existing_columns}")
            except Exception as e:
                logger.warning(f"Could not read existing row: {e}")
        logger.info(f"[PERF] upsert_data: Read existing row took {time.time() - step_start:.3f}s")
        
        # If we found existing data, use its column set; otherwise use table schema
        if existing_columns:
            # Only use columns that exist in BOTH the DataFrame AND the existing data
            columns_to_use = [col for col in df.columns if col in existing_columns]
            
            # Ensure join columns are included
            for col in join_cols:
                if col not in columns_to_use:
                    columns_to_use.insert(0, col)
            
            logger.info(f"Using columns for upsert: {columns_to_use}")
            df = df[columns_to_use]
        else:
            # No existing row - use table schema (new insert via upsert)
            schema_column_order = [field.name for field in current_schema.fields]
            schema_field_names = set(schema_column_order)
            columns_to_remove = [col for col in df.columns if col not in schema_field_names]
            if columns_to_remove:
                df = df.drop(columns=columns_to_remove)
            for col in schema_column_order:
                if col not in df.columns:
                    df[col] = None
            df = df[schema_column_order]
        logger.info(f"[PERF] upsert_data: Column ordering took {time.time() - step_start:.3f}s")
        
        # Convert timestamp columns from nanoseconds to microseconds (Iceberg requirement)
        step_start = time.time()
        # Pandas defaults to timestamp[ns] but Iceberg only supports timestamp[us]
        # Note: Only convert actual timestamp columns, not date columns (date32)
        table_schema = table.schema().as_arrow()
        schema_field_types = {field.name: field.type for field in table_schema}
        
        for col in df.columns:
            if col in schema_field_types:
                field_type = schema_field_types[col]
                # Check if this is a timestamp field (not a date field)
                if pa.types.is_timestamp(field_type):
                    # Only convert if it's actually a datetime/timestamp column
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        # Convert to datetime64[us] (microseconds) instead of datetime64[ns] (nanoseconds)
                        df[col] = df[col].astype('datetime64[us]')
                elif pa.types.is_date(field_type):
                    # Ensure date columns stay as dates (not timestamps)
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        # Convert timestamp to date
                        df[col] = pd.to_datetime(df[col]).dt.date
                    # If column is None/NaN, force to object dtype to prevent timestamp[ns] inference
                    elif df[col].isna().all() or df[col].dtype != 'object':
                        # Force to object dtype to hold date objects (not timestamp[ns])
                        df[col] = df[col].astype('object')
        
        # Convert to PyArrow table - let pandas handle type inference
        step_start = time.time()
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        logger.info(f"[PERF] upsert_data: PyArrow table creation took {time.time() - step_start:.3f}s")
        
        # Perform upsert
        step_start = time.time()
        table.upsert(arrow_table, join_cols=join_cols)
        logger.info(f"[PERF] upsert_data: table.upsert() took {time.time() - step_start:.3f}s")
        
        total_time = time.time() - start_time
        logger.info(f"[PERF] upsert_data: TOTAL TIME {total_time:.3f}s")
        
    except Exception as e:
        logger.error(f"Failed to upsert data to {'.'.join((*namespace, table_name))}: {e}", exc_info=True)
        raise

# USAGE: upsert_data_with_schema_cast() is used in:
# - app/services/expense_service.py
# - app/api/tenants.py
# - app/scripts/backfill_document_property_id.py
# - app/api/landlord_references.py
# - app/api/units.py
def upsert_data_with_schema_cast(namespace: Tuple[str, ...], table_name: str, data: pd.DataFrame, join_cols: list[str] = None):
    """
    Upsert data to an Iceberg table with explicit schema casting.
    
    This function is similar to upsert_data but casts the PyArrow table to the table's schema
    before upserting. This ensures required fields are properly marked and prevents schema
    compatibility errors where required fields are inferred as optional.
    
    Args:
        namespace: Table namespace tuple
        table_name: Name of the table
        data: DataFrame to upsert
        join_cols: Columns to use for join (default: ["id"])
    """
    import time
    start_time = time.time()
    
    if join_cols is None:
        join_cols = ["id"]
        
    try:
        step_start = time.time()
        table = load_table(namespace, table_name)
        current_schema = table.schema()
        logger.info(f"[PERF] upsert_data_with_schema_cast: load_table took {time.time() - step_start:.3f}s")
        
        # CRITICAL FIX: Convert timestamp columns IMMEDIATELY after copying the DataFrame
        # Pandas creates timestamp[ns] by default, but Iceberg only supports timestamp[us]
        step_start = time.time()
        df = data.copy()
        logger.info(f"[PERF] upsert_data_with_schema_cast: DataFrame copy took {time.time() - step_start:.3f}s")
        
        # Get schema first to know which columns are timestamps vs dates
        table_schema = table.schema().as_arrow()
        schema_field_types = {field.name: field.type for field in table_schema}
        
        # Convert all datetime columns based on their schema type BEFORE any other operations
        for col in df.columns:
            if col in schema_field_types:
                field_type = schema_field_types[col]
                # Check if this is a timestamp field (not a date field)
                if pa.types.is_timestamp(field_type):
                    # Only convert if it's actually a datetime/timestamp column
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        # Convert to datetime64[us] (microseconds) instead of datetime64[ns] (nanoseconds)
                        df[col] = df[col].astype('datetime64[us]')
                elif pa.types.is_date(field_type):
                    # Ensure date columns stay as dates (not timestamps)
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        # Convert timestamp to date
                        df[col] = pd.to_datetime(df[col]).dt.date
                    # If column is None/NaN, force to object dtype to prevent timestamp[ns] inference
                    elif df[col].isna().all() or df[col].dtype != 'object':
                        # Force to object dtype to hold date objects (not timestamp[ns])
                        df[col] = df[col].astype('object')
        logger.info(f"[PERF] upsert_data_with_schema_cast: First timestamp conversion took {time.time() - step_start:.3f}s")
        
        # Check for duplicates in join columns
        step_start = time.time()
        if len(df) > 1:
            duplicates = df.duplicated(subset=join_cols)
            if duplicates.any():
                raise ValueError(f"Duplicate rows found in source dataset based on the key columns {join_cols}. No upsert executed")
        logger.info(f"[PERF] upsert_data_with_schema_cast: Duplicate check took {time.time() - step_start:.3f}s")
        
        # Use table schema directly - no need to read existing row since we're building full record
        # This avoids expensive table scans for single-row updates
        step_start = time.time()
        schema_column_order = [field.name for field in current_schema.fields]
        schema_field_names = set(schema_column_order)
        
        # Remove any columns that don't exist in the schema
        columns_to_remove = [col for col in df.columns if col not in schema_field_names]
        if columns_to_remove:
            df = df.drop(columns=columns_to_remove)
        
        # Ensure all schema columns are present (add None for missing ones)
        for col in schema_column_order:
            if col not in df.columns:
                df[col] = None
        
        # Reorder DataFrame columns to match schema order exactly
        df = df[schema_column_order]
        logger.info(f"[PERF] upsert_data_with_schema_cast: Column ordering took {time.time() - step_start:.3f}s")
        
        # Convert timestamp columns from nanoseconds to microseconds (Iceberg requirement)
        # Pandas defaults to timestamp[ns] but Iceberg only supports timestamp[us]
        # Note: Only convert actual timestamp columns, not date columns (date32)
        step_start = time.time()
        table_schema = table.schema().as_arrow()
        schema_field_types = {field.name: field.type for field in table_schema}
        
        for col in df.columns:
            if col in schema_field_types:
                field_type = schema_field_types[col]
                # Check if this is a timestamp field (not a date field)
                if pa.types.is_timestamp(field_type):
                    # Only convert if it's actually a datetime/timestamp column
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        # Convert to datetime64[us] (microseconds) instead of datetime64[ns] (nanoseconds)
                        df[col] = df[col].astype('datetime64[us]')
                elif pa.types.is_date(field_type):
                    # Ensure date columns stay as dates (not timestamps)
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        # Convert timestamp to date
                        df[col] = pd.to_datetime(df[col]).dt.date
                    # If column is None/NaN, force to object dtype to prevent timestamp[ns] inference
                    elif df[col].isna().all() or df[col].dtype != 'object':
                        # Force to object dtype to hold date objects (not timestamp[ns])
                        df[col] = df[col].astype('object')
        logger.info(f"[PERF] upsert_data_with_schema_cast: Second timestamp conversion took {time.time() - step_start:.3f}s")
        
        # Convert to PyArrow table - let pandas handle type inference
        step_start = time.time()
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        logger.info(f"[PERF] upsert_data_with_schema_cast: PyArrow table creation took {time.time() - step_start:.3f}s")
        
        # CRITICAL: Cast to table schema BEFORE upsert to ensure required fields are properly marked
        # This prevents schema compatibility errors where required fields are inferred as optional
        step_start = time.time()
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        logger.info(f"[PERF] upsert_data_with_schema_cast: Schema cast took {time.time() - step_start:.3f}s")
        
        # Perform upsert
        step_start = time.time()
        table.upsert(arrow_table, join_cols=join_cols)
        logger.info(f"[PERF] upsert_data_with_schema_cast: table.upsert() took {time.time() - step_start:.3f}s")
        
        total_time = time.time() - start_time
        logger.info(f"[PERF] upsert_data_with_schema_cast: TOTAL TIME {total_time:.3f}s")
        
    except Exception as e:
        logger.error(f"Failed to upsert data with schema cast to {'.'.join((*namespace, table_name))}: {e}", exc_info=True)
        raise


# USAGE: update_walkthrough_data() is used ONLY in:
# - app/api/walkthroughs.py
def update_walkthrough_data(walkthrough_id: str, data: pd.DataFrame):
    """
    Update walkthrough data using delete+append pattern.
    
    This is a walkthroughs-specific function that handles the walkthroughs table
    using a delete+append pattern. It should NOT be used for other tables.
    
    Args:
        walkthrough_id: The ID of the walkthrough to update
        data: DataFrame containing the walkthrough data to update
    """
    from pyiceberg.expressions import EqualTo
    
    NAMESPACE = ("investflow",)
    WALKTHROUGHS_TABLE = "walkthroughs"
    
    try:
        table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        schema_columns = [field.name for field in table.schema().fields]
        
        # Ensure DataFrame has all schema columns in correct order
        data = data.reindex(columns=schema_columns, fill_value=None)
        
        # Convert timestamp columns from nanoseconds to microseconds
        for col in data.columns:
            if pd.api.types.is_datetime64_any_dtype(data[col]):
                data[col] = data[col].astype('datetime64[us]')
        
        # Delete existing row(s) for this walkthrough ID
        table.delete(EqualTo("id", str(walkthrough_id)))
        
        # Convert to PyArrow table and cast to schema
        arrow_table = pa.Table.from_pandas(data)
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        
        # Append updated walkthrough
        table.append(arrow_table)
        
    except Exception as e:
        logger.error(f"Failed to update walkthrough {walkthrough_id}: {e}", exc_info=True)
        raise


# USAGE: create_walkthrough_data() is used ONLY in:
# - app/api/walkthroughs.py
def create_walkthrough_data(record: dict):
    """
    Create a new walkthrough record using upsert pattern.
    
    This is a walkthroughs-specific function that handles the walkthroughs table
    for new record creation. It should NOT be used for other tables.
    
    Args:
        record: Dictionary containing the walkthrough data to create
    """
    NAMESPACE = ("investflow",)
    WALKTHROUGHS_TABLE = "walkthroughs"
    
    try:
        table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        table_schema = table.schema().as_arrow()
        
        # Handle type conversions for the record
        schema_field_types = {field.name: field.type for field in table_schema}
        
        for col_name, value in record.items():
            if col_name not in schema_field_types:
                continue
                
            field_type = schema_field_types[col_name]
            
            # Handle date fields - ensure date objects (not datetime/timestamp)
            if pa.types.is_date(field_type):
                if value is None:
                    record[col_name] = None
                elif isinstance(value, (datetime, pd.Timestamp)):
                    record[col_name] = value.date()
                elif isinstance(value, date):
                    record[col_name] = value
                else:
                    record[col_name] = None
            # For timestamp fields, ensure datetime objects
            elif pa.types.is_timestamp(field_type):
                if value is None:
                    record[col_name] = None
                elif isinstance(value, pd.Timestamp):
                    record[col_name] = value.to_pydatetime()
                elif isinstance(value, datetime):
                    record[col_name] = value
                else:
                    record[col_name] = value
        
        # Create PyArrow table from single record with explicit schema
        arrow_table = pa.Table.from_pylist([record], schema=table_schema)
        
        # Use table.upsert() directly for new records
        table.upsert(arrow_table, join_cols=["id"])
        
    except Exception as e:
        logger.error(f"Failed to create walkthrough: {e}", exc_info=True)
        raise


