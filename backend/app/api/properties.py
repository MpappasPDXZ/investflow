"""API routes for property management"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Union
from uuid import UUID
import uuid
import pandas as pd
from decimal import Decimal
from datetime import date, datetime, time, timezone
import pyarrow as pa
from pyiceberg.expressions import EqualTo

from app.core.dependencies import get_current_user
from app.schemas.property import (
    PropertyCreate, PropertyUpdate, PropertyResponse, PropertyListResponse
)
from app.core.iceberg import get_catalog, read_table, read_table_filtered, table_exists
from app.core.logging import get_logger
from app.api.vacancy_utils import create_or_update_vacancy_expenses
from app.api.tax_savings_utils import create_or_update_tax_savings

NAMESPACE = ("investflow",)
TABLE_NAME = "properties"

router = APIRouter(prefix="/properties", tags=["properties"])
logger = get_logger(__name__)

# Strict field order for properties table (must match Iceberg schema exactly)
PROPERTIES_FIELD_ORDER = [
    "id",
    "user_id",
    "display_name",
    "property_status",
    "purchase_date",
    "monthly_rent_to_income_ratio",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "zip_code",
    "property_type",
    "has_units",
    "notes",
    "is_active",
    "purchase_price",
    "square_feet",
    "down_payment",
    "cash_invested",
    "current_market_value",
    "vacancy_rate",
    "unit_count",
    "bedrooms",
    "bathrooms",
    "year_built",
    "current_monthly_rent",
    "created_at",
    "updated_at",
]


# ========== DEDICATED PROPERTIES ICEBERG FUNCTIONS ==========

def _load_properties_table():
    """Load the properties Iceberg table (dedicated function)"""
    catalog = get_catalog()
    table_identifier = (*NAMESPACE, TABLE_NAME)
    return catalog.load_table(table_identifier)


def _read_properties_table() -> pd.DataFrame:
    """Read all properties from Iceberg table (dedicated function)"""
    try:
        table = _load_properties_table()
        scan = table.scan()
        arrow_table = scan.to_arrow()
        return arrow_table.to_pandas()
    except Exception as e:
        logger.error(f"Failed to read properties table: {e}", exc_info=True)
        raise


def _append_property(property_dict: dict):
    """Append a property with strict field ordering (dedicated function)"""
    try:
        logger.info(f"📋 [PROPERTY] _append_property: Starting append with property_dict keys: {list(property_dict.keys())}")
        table = _load_properties_table()
        current_schema = table.schema()
        
        # Build DataFrame with fields in exact order
        ordered_dict = {}
        for field_name in PROPERTIES_FIELD_ORDER:
            if field_name in property_dict:
                ordered_dict[field_name] = property_dict[field_name]
            else:
                ordered_dict[field_name] = None
        
        df = pd.DataFrame([ordered_dict])
        logger.info(f"📋 [PROPERTY] _append_property: Initial DataFrame dtypes: {df.dtypes.to_dict()}")
        
        # Ensure DataFrame columns are in exact order
        df = df[PROPERTIES_FIELD_ORDER]
        
        # Convert timestamp columns to microseconds
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                try:
                    # If already a Timestamp, ensure it's timezone-naive and in microseconds
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        # Already datetime64, just ensure microseconds precision
                        df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None).dt.floor('us')
                    else:
                        # Try to convert to datetime, handling various input types
                        df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
                        if df[col].notna().any():
                            df[col] = df[col].dt.tz_localize(None).dt.floor('us')
                except Exception as e:
                    logger.error(f"❌ [PROPERTY] Error converting timestamp column {col}: {e}", exc_info=True)
                    raise
        
        # Convert date columns to date objects
        if 'purchase_date' in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df['purchase_date']):
                df['purchase_date'] = pd.to_datetime(df['purchase_date']).dt.date
            elif df['purchase_date'].dtype == 'object':
                # Already date objects
                pass
        
        # Convert decimal columns to proper types
        from decimal import Decimal as PythonDecimal
        decimal_cols = ['monthly_rent_to_income_ratio', 'vacancy_rate', 'bathrooms', 'current_monthly_rent']
        for col in decimal_cols:
            if col in df.columns:
                def to_decimal(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return PythonDecimal(str(float(x)))
                    except (ValueError, TypeError):
                        return None
                df[col] = df[col].apply(to_decimal)
        
        # Convert long/integer columns
        long_cols = ['purchase_price', 'square_feet', 'down_payment', 'cash_invested', 'current_market_value', 'unit_count', 'bedrooms', 'year_built']
        for col in long_cols:
            if col in df.columns:
                def to_long(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        # Convert Decimal to int
                        if isinstance(x, PythonDecimal):
                            return int(x)
                        return int(float(x))
                    except (ValueError, TypeError):
                        return None
                df[col] = df[col].apply(to_long)
        
        # Convert boolean columns
        if 'has_units' in df.columns:
            df['has_units'] = df['has_units'].astype(bool) if pd.notna(df['has_units']).any() else False
        if 'is_active' in df.columns:
            df['is_active'] = df['is_active'].astype(bool) if pd.notna(df['is_active']).any() else True
        
        # Ensure DataFrame columns match schema order and all schema columns are present
        schema_column_order = [field.name for field in current_schema.fields]
        schema_field_names = set(schema_column_order)
        
        # Add missing columns with None values
        for col in schema_column_order:
            if col not in df.columns:
                df[col] = None
        
        # Remove any columns that don't exist in schema
        columns_to_remove = [col for col in df.columns if col not in schema_field_names]
        if columns_to_remove:
            logger.warning(f"Removing columns from DataFrame that don't exist in table schema: {columns_to_remove}")
            df = df.drop(columns=columns_to_remove)
        
        # Reorder to match schema order
        df = df[schema_column_order]
        
        # Final timestamp conversion check - ensure microseconds precision
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                # Convert to datetime64[us] (microseconds) instead of datetime64[ns] (nanoseconds)
                df[col] = df[col].astype('datetime64[us]')
        
        logger.info(f"📋 [PROPERTY] _append_property: Final DataFrame dtypes before PyArrow: {df.dtypes.to_dict()}")
        
        # Convert to PyArrow and cast to schema
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        table_schema = table.schema().as_arrow()
        logger.info(f"📋 [PROPERTY] _append_property: PyArrow table created, casting to schema")
        arrow_table = arrow_table.cast(table_schema)
        
        logger.info(f"📋 [PROPERTY] _append_property: Appending to table")
        table.append(arrow_table)
        logger.info(f"✅ [PROPERTY] _append_property: Successfully appended property")
    except Exception as e:
        logger.error(f"Failed to append property: {e}", exc_info=True)
        raise


def _upsert_property(property_df: pd.DataFrame):
    """Upsert a property with strict field ordering (dedicated function)"""
    try:
        table = _load_properties_table()
        current_schema = table.schema()
        
        logger.info(f"📋 [PROPERTY] _upsert_property: Input DataFrame columns: {list(property_df.columns)}")
        logger.info(f"📋 [PROPERTY] _upsert_property: Expected field order: {PROPERTIES_FIELD_ORDER}")
        
        # Ensure DataFrame has all required fields in exact order
        for field_name in PROPERTIES_FIELD_ORDER:
            if field_name not in property_df.columns:
                property_df[field_name] = None
        
        # Reorder columns to match exact schema order
        property_df = property_df[PROPERTIES_FIELD_ORDER]
        logger.info(f"📋 [PROPERTY] _upsert_property: Reordered columns: {list(property_df.columns)}")
        
        # Convert timestamp columns to microseconds
        for col in ['created_at', 'updated_at']:
            if col in property_df.columns:
                try:
                    # If already a Timestamp, ensure it's timezone-naive and in microseconds
                    if pd.api.types.is_datetime64_any_dtype(property_df[col]):
                        # Already datetime64, just ensure microseconds precision
                        property_df[col] = pd.to_datetime(property_df[col], utc=True).dt.tz_localize(None).dt.floor('us')
                    else:
                        # Try to convert to datetime, handling various input types
                        property_df[col] = pd.to_datetime(property_df[col], errors='coerce', utc=True)
                        if property_df[col].notna().any():
                            property_df[col] = property_df[col].dt.tz_localize(None).dt.floor('us')
                except Exception as e:
                    logger.error(f"❌ [PROPERTY] Error converting timestamp column {col}: {e}", exc_info=True)
                    raise
        
        # Convert date columns to date objects
        if 'purchase_date' in property_df.columns:
            try:
                if pd.api.types.is_datetime64_any_dtype(property_df['purchase_date']):
                    property_df['purchase_date'] = pd.to_datetime(property_df['purchase_date']).dt.date
                elif isinstance(property_df['purchase_date'].iloc[0] if len(property_df) > 0 else None, pd.Timestamp):
                    property_df['purchase_date'] = property_df['purchase_date'].dt.date
                # If already date objects, leave as is
            except Exception as e:
                logger.warning(f"⚠️ [PROPERTY] Error converting date column purchase_date: {e}")
        
        # Convert decimal columns
        from decimal import Decimal as PythonDecimal
        decimal_cols = ['monthly_rent_to_income_ratio', 'vacancy_rate', 'bathrooms', 'current_monthly_rent']
        for col in decimal_cols:
            if col in property_df.columns:
                try:
                    property_df[col] = pd.to_numeric(property_df[col], errors='coerce')
                    def to_decimal(x):
                        if pd.isna(x) or x is None:
                            return None
                        try:
                            return PythonDecimal(str(float(x)))
                        except (ValueError, TypeError):
                            return None
                    property_df[col] = property_df[col].apply(to_decimal)
                except Exception as e:
                    logger.warning(f"⚠️ [PROPERTY] Error converting decimal column {col}: {e}")
        
        # Convert long/integer columns
        long_cols = ['purchase_price', 'square_feet', 'down_payment', 'cash_invested', 'current_market_value', 'unit_count', 'bedrooms', 'year_built']
        for col in long_cols:
            if col in property_df.columns:
                try:
                    def to_long(x):
                        if pd.isna(x) or x is None:
                            return None
                        try:
                            if isinstance(x, PythonDecimal):
                                return int(x)
                            if isinstance(x, (int, float)):
                                return int(x)
                            return int(float(x))
                        except (ValueError, TypeError):
                            return None
                    property_df[col] = property_df[col].apply(to_long)
                except Exception as e:
                    logger.warning(f"⚠️ [PROPERTY] Error converting long column {col}: {e}")
        
        # Convert boolean columns
        if 'has_units' in property_df.columns:
            try:
                property_df['has_units'] = property_df['has_units'].astype(bool)
            except Exception as e:
                logger.warning(f"⚠️ [PROPERTY] Error converting boolean column has_units: {e}")
        if 'is_active' in property_df.columns:
            try:
                property_df['is_active'] = property_df['is_active'].astype(bool)
            except Exception as e:
                logger.warning(f"⚠️ [PROPERTY] Error converting boolean column is_active: {e}")
        
        logger.info(f"📋 [PROPERTY] _upsert_property: Final DataFrame dtypes: {property_df.dtypes.to_dict()}")
        
        # Convert to PyArrow and cast to schema
        arrow_table = pa.Table.from_pandas(property_df)
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        
        logger.info(f"📋 [PROPERTY] _upsert_property: Performing upsert with join_cols=['id']")
        table.upsert(arrow_table, join_cols=["id"])
        logger.info(f"✅ [PROPERTY] _upsert_property: Upsert successful")
    except Exception as e:
        logger.error(f"❌ [PROPERTY] Failed to upsert property: {e}", exc_info=True)
        raise


def parse_date_midday(date_value: Union[str, date, datetime, pd.Timestamp]) -> pd.Timestamp:
    """
    Parse date using Midday Strategy to prevent timezone shifting.
    Sets time to 12:00:00 (noon) to provide buffer against timezone offsets.
    """
    if date_value is None:
        return None
    
    # If already a pandas Timestamp, extract the date part
    if isinstance(date_value, pd.Timestamp):
        date_value = date_value.date()
    
    # If it's a datetime, extract the date part
    if isinstance(date_value, datetime):
        date_value = date_value.date()
    
    # If it's a string, parse it to a date
    if isinstance(date_value, str):
        date_value = datetime.strptime(date_value, "%Y-%m-%d").date()
    
    # Now date_value should be a date object
    # Combine with midday time (12:00:00)
    midday_datetime = datetime.combine(date_value, time(12, 0, 0))
    
    # Convert to pandas Timestamp
    return pd.Timestamp(midday_datetime)


@router.post("", response_model=PropertyResponse, status_code=201)
async def create_property_endpoint(
    property_data: PropertyCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new property in Iceberg"""
    try:
        user_id = current_user["sub"]  # Already a string
        property_id = str(uuid.uuid4())
        # Use datetime.utcnow() like expenses do
        now = datetime.utcnow()
        
        # Create property record with strict field ordering
        purchase_date_value = property_data.purchase_date if property_data.purchase_date else date(2025, 10, 23)
        
        # Build record with ALL fields from PROPERTIES_FIELD_ORDER to ensure nothing is missing
        # Use getattr with defaults to ensure all fields are included even if None
        record = {
            "id": property_id,
            "user_id": user_id,
            "display_name": getattr(property_data, "display_name", None),
            "property_status": getattr(property_data, "property_status", None) or "evaluating",
            "purchase_date": purchase_date_value,
            "monthly_rent_to_income_ratio": Decimal(str(property_data.monthly_rent_to_income_ratio)) if property_data.monthly_rent_to_income_ratio is not None else None,
            "address_line1": getattr(property_data, "address_line1", None),
            "address_line2": getattr(property_data, "address_line2", None),
            "city": getattr(property_data, "city", None),
            "state": getattr(property_data, "state", None),
            "zip_code": getattr(property_data, "zip_code", None),
            "property_type": getattr(property_data, "property_type", None),
            "has_units": getattr(property_data, "has_units", None) if getattr(property_data, "has_units", None) is not None else False,
            "notes": getattr(property_data, "notes", None),
            "is_active": True,
            "purchase_price": int(property_data.purchase_price) if property_data.purchase_price is not None else None,
            "square_feet": int(property_data.square_feet) if property_data.square_feet is not None else None,
            "down_payment": int(property_data.down_payment) if property_data.down_payment is not None else None,
            "cash_invested": int(property_data.cash_invested) if property_data.cash_invested is not None else None,
            "current_market_value": int(property_data.current_market_value) if property_data.current_market_value is not None else None,
            "vacancy_rate": Decimal(str(property_data.vacancy_rate)) if property_data.vacancy_rate is not None else Decimal("0.07"),
            "unit_count": int(property_data.unit_count) if property_data.unit_count is not None else None,
            "bedrooms": int(property_data.bedrooms) if property_data.bedrooms is not None else None,
            "bathrooms": Decimal(str(property_data.bathrooms)) if property_data.bathrooms is not None else None,
            "year_built": int(property_data.year_built) if property_data.year_built is not None else None,
            "current_monthly_rent": Decimal(str(property_data.current_monthly_rent)) if property_data.current_monthly_rent is not None else None,
            "created_at": now,
            "updated_at": now,
        }
        
        # Ensure ALL fields from PROPERTIES_FIELD_ORDER are present (even if None)
        for field_name in PROPERTIES_FIELD_ORDER:
            if field_name not in record:
                record[field_name] = None
        
        # Write to Iceberg - build record in schema order with proper type conversions
        table = _load_properties_table()
        table_schema = table.schema().as_arrow()
        
        logger.info(f"📋 [PROPERTY] Schema fields: {[f.name for f in table_schema]}")
        logger.info(f"📋 [PROPERTY] Record keys: {list(record.keys())}")
        
        # Build record in schema order with proper type conversions (like leases do)
        prepared_record = {}
        for field in table_schema:
            col_name = field.name
            value = record.get(col_name)  # Returns None if key doesn't exist
            field_type = field.type
            
            # If value is missing from record, handle based on nullable requirement
            if col_name not in record:
                if not field.nullable:
                    logger.error(f"❌ [PROPERTY] Missing required field: {col_name}")
                    logger.error(f"❌ [PROPERTY] Available record keys: {list(record.keys())}")
                    raise ValueError(f"Missing required field: {col_name}")
                # For nullable fields, set to None
                prepared_record[col_name] = None
                continue
            
            # CRITICAL: For date fields, ensure date objects (not datetime/timestamp)
            if pa.types.is_date(field_type):
                if value is None:
                    prepared_record[col_name] = None
                elif isinstance(value, (datetime, pd.Timestamp)):
                    prepared_record[col_name] = value.date()
                elif isinstance(value, date):
                    prepared_record[col_name] = value
                else:
                    logger.warning(f"⚠️ [PROPERTY] Unexpected type for date field {col_name}: {type(value)}")
                    prepared_record[col_name] = None
            # For timestamp fields, ensure datetime objects
            elif pa.types.is_timestamp(field_type):
                if value is None:
                    prepared_record[col_name] = None
                elif isinstance(value, pd.Timestamp):
                    prepared_record[col_name] = value.to_pydatetime()
                elif isinstance(value, datetime):
                    prepared_record[col_name] = value
                else:
                    logger.warning(f"⚠️ [PROPERTY] Unexpected type for timestamp field {col_name}: {type(value)}")
                    prepared_record[col_name] = value
            # For double/float fields, convert Decimal to float
            # Check for float64 (double) or float32 - use multiple methods to detect
            elif (
                pa.types.is_floating(field_type) or 
                str(field_type) in ['double', 'float64', 'float32', 'float'] or
                'float' in str(field_type).lower()
            ):
                if value is None:
                    prepared_record[col_name] = None
                elif isinstance(value, Decimal):
                    prepared_record[col_name] = float(value)
                    logger.info(f"🔧 [PROPERTY] Converted {col_name} from Decimal to float: {value} -> {float(value)}")
                elif isinstance(value, (int, float)):
                    prepared_record[col_name] = float(value)
                else:
                    prepared_record[col_name] = value
            # For decimal128 fields, keep as Decimal
            elif pa.types.is_decimal(field_type):
                if value is None:
                    prepared_record[col_name] = None
                elif isinstance(value, Decimal):
                    prepared_record[col_name] = value
                elif isinstance(value, (int, float)):
                    prepared_record[col_name] = Decimal(str(value))
                else:
                    prepared_record[col_name] = value
            else:
                prepared_record[col_name] = value
        
        logger.info(f"📋 [PROPERTY] Prepared record keys: {list(prepared_record.keys())}")
        
        # Validate all schema fields are present
        schema_field_names = {f.name for f in table_schema}
        prepared_record_keys = set(prepared_record.keys())
        missing_fields = schema_field_names - prepared_record_keys
        extra_fields = prepared_record_keys - schema_field_names
        
        if missing_fields:
            logger.error(f"❌ [PROPERTY] Missing fields in prepared_record: {missing_fields}")
            logger.error(f"❌ [PROPERTY] Schema fields: {schema_field_names}")
            logger.error(f"❌ [PROPERTY] Prepared record fields: {prepared_record_keys}")
            raise ValueError(f"Missing fields in prepared record: {missing_fields}")
        
        if extra_fields:
            logger.warning(f"⚠️ [PROPERTY] Extra fields in prepared_record (will be ignored): {extra_fields}")
        
        # Create table from single record with explicit schema - this ensures exact types
        try:
            logger.info(f"📋 [PROPERTY] Creating PyArrow table with {len(prepared_record)} fields")
            arrow_table = pa.Table.from_pylist([prepared_record], schema=table_schema)
            logger.info(f"✅ [PROPERTY] PyArrow table created successfully")
        except Exception as e:
            logger.error(f"❌ [PROPERTY] Failed to create PyArrow table: {e}", exc_info=True)
            logger.error(f"❌ [PROPERTY] Prepared record types: {[(k, type(v).__name__) for k, v in prepared_record.items()]}")
            logger.error(f"❌ [PROPERTY] Schema field types: {[(f.name, str(f.type)) for f in table_schema]}")
            raise
        
        try:
            table.append(arrow_table)
            logger.info(f"✅ [PROPERTY] Successfully appended to table")
        except Exception as e:
            logger.error(f"❌ [PROPERTY] Failed to append to table: {e}", exc_info=True)
            raise
        
        logger.info(f"Created property: {property_id}")
        
        # Create vacancy expenses if square footage is available
        if property_data.square_feet and property_data.square_feet > 0:
            vacancy_rate = record["vacancy_rate"]
            await create_or_update_vacancy_expenses(
                property_id=property_id,
                square_feet=property_data.square_feet,
                vacancy_rate=vacancy_rate
            )
        
        # Create tax savings (depreciation) revenue
        # Use current_market_value if available, otherwise fall back to purchase_price
        property_value = property_data.current_market_value if property_data.current_market_value is not None else property_data.purchase_price
        if property_value is not None:
            await create_or_update_tax_savings(
                property_id=property_id,
                user_id=user_id,
                current_market_value=Decimal(str(property_value)),
                purchase_date=record["purchase_date"]
            )
        
        # Convert to response (UUID conversion)
        response_dict = record.copy()
        response_dict["id"] = UUID(property_id)
        response_dict["user_id"] = UUID(user_id)
        response_dict["purchase_price"] = property_data.purchase_price
        response_dict["down_payment"] = property_data.down_payment
        response_dict["current_market_value"] = property_data.current_market_value
        response_dict["monthly_rent_to_income_ratio"] = property_data.monthly_rent_to_income_ratio
        if property_data.bathrooms:
            response_dict["bathrooms"] = property_data.bathrooms
        if property_data.current_monthly_rent:
            response_dict["current_monthly_rent"] = property_data.current_monthly_rent
        
        return PropertyResponse(**response_dict)
    except Exception as e:
        logger.error(f"Error creating property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=PropertyListResponse)
async def list_properties_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """List all properties for the current user from Iceberg (including shared properties)"""
    import time
    endpoint_start = time.time()
    logger.info(f"⏱️ [PERF] list_properties_endpoint started")
    
    try:
        user_id = current_user["sub"]  # Already a string
        user_email = current_user["email"]
        
        table_exists_start = time.time()
        if not table_exists(NAMESPACE, TABLE_NAME):
            return PropertyListResponse(items=[], total=0, page=1, limit=limit)
        logger.info(f"⏱️ [PERF] table_exists took {time.time() - table_exists_start:.2f}s")
        
        # Read all properties
        read_start = time.time()
        df = read_table(NAMESPACE, TABLE_NAME)
        logger.info(f"⏱️ [PERF] read_table(properties) took {time.time() - read_start:.2f}s")
        
        # Get shared user IDs (bidirectional)
        sharing_start = time.time()
        from app.api.sharing_utils import get_shared_user_ids
        logger.info(f"🔐 [INSPECTIONS] Checking user access before populating the dropdown under Inspections\nmanage property inspections")
        shared_user_ids = get_shared_user_ids(user_id, user_email)
        logger.info(f"⏱️ [PERF] get_shared_user_ids took {time.time() - sharing_start:.2f}s")
        
        # Filter: properties owned by user OR owned by shared users
        filter_start = time.time()
        if len(shared_user_ids) > 0:
            user_properties = df[
                ((df["user_id"] == user_id) | (df["user_id"].isin(shared_user_ids))) &
                (df["is_active"] == True)
            ]
        else:
            user_properties = df[(df["user_id"] == user_id) & (df["is_active"] == True)]
        logger.info(f"⏱️ [PERF] Filtering properties took {time.time() - filter_start:.2f}s")
        
        total = len(user_properties)
        
        # Apply pagination
        paginated = user_properties.iloc[skip:skip + limit]
        
        # Convert to PropertyResponse objects
        convert_start = time.time()
        items = []
        for _, row in paginated.iterrows():
            prop_dict = {
                "id": UUID(str(row["id"])),
                "user_id": UUID(str(row["user_id"])),
                "display_name": row.get("display_name"),
                "purchase_price": Decimal(str(row["purchase_price"])),
                "purchase_date": row.get("purchase_date") if pd.notna(row.get("purchase_date")) else None,
                "down_payment": Decimal(str(row["down_payment"])) if pd.notna(row.get("down_payment")) else None,
                "cash_invested": Decimal(str(row["cash_invested"])) if pd.notna(row.get("cash_invested")) else None,
                "current_market_value": Decimal(str(row["current_market_value"])) if pd.notna(row.get("current_market_value")) else None,
                "property_status": row.get("property_status", "evaluating"),
                "vacancy_rate": Decimal(str(row["vacancy_rate"])) if pd.notna(row.get("vacancy_rate")) else Decimal("0.07"),
                "monthly_rent_to_income_ratio": Decimal(str(row["monthly_rent_to_income_ratio"])) if pd.notna(row.get("monthly_rent_to_income_ratio")) else Decimal("2.75"),
                "address_line1": row.get("address_line1"),
                "address_line2": row.get("address_line2"),
                "city": row.get("city"),
                "state": row.get("state"),
                "zip_code": row.get("zip_code"),
                "property_type": row.get("property_type"),
                "bedrooms": int(row["bedrooms"]) if pd.notna(row.get("bedrooms")) else None,
                "bathrooms": Decimal(str(row["bathrooms"])) if pd.notna(row.get("bathrooms")) else None,
                "square_feet": int(row["square_feet"]) if pd.notna(row.get("square_feet")) else None,
                "year_built": int(row["year_built"]) if pd.notna(row.get("year_built")) else None,
                "current_monthly_rent": Decimal(str(row["current_monthly_rent"])) if pd.notna(row.get("current_monthly_rent")) else None,
                "notes": row.get("notes"),
                "is_active": bool(row["is_active"]) if pd.notna(row.get("is_active")) else True,
                "created_at": row["created_at"] if pd.notna(row.get("created_at")) else pd.Timestamp.now(),
                "updated_at": row["updated_at"] if pd.notna(row.get("updated_at")) else pd.Timestamp.now(),
            }
            items.append(PropertyResponse(**prop_dict))
        logger.info(f"⏱️ [PERF] Converting to PropertyResponse objects took {time.time() - convert_start:.2f}s")
        
        total_time = time.time() - endpoint_start
        logger.info(f"⏱️ [PERF] list_properties_endpoint completed in {total_time:.2f}s")
        
        return PropertyListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            limit=limit
        )
    except Exception as e:
        total_time = time.time() - endpoint_start
        logger.error(f"⏱️ [PERF] list_properties_endpoint failed after {total_time:.2f}s: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property_endpoint(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a property by ID from Iceberg (checks ownership and sharing)"""
    try:
        user_id = current_user["sub"]  # Already a string
        user_email = current_user["email"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Read table and find property
        df = read_table(NAMESPACE, TABLE_NAME)
        property_rows = df[df["id"] == property_id]
        
        if len(property_rows) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_row = property_rows.iloc[0]
        property_user_id = str(property_row["user_id"])
        
        # Check access: owner OR bidirectional share
        from app.api.sharing_utils import user_has_property_access
        if not user_has_property_access(property_user_id, user_id, user_email):
            raise HTTPException(status_code=404, detail="Property not found")
        
        row = property_rows.iloc[0]
        
        # Convert to response
        prop_dict = {
            "id": UUID(str(row["id"])),
            "user_id": UUID(str(row["user_id"])),
            "display_name": row.get("display_name"),
            "purchase_price": Decimal(str(row["purchase_price"])),
            "purchase_date": row.get("purchase_date") if pd.notna(row.get("purchase_date")) else None,
            "down_payment": Decimal(str(row["down_payment"])) if pd.notna(row.get("down_payment")) else None,
            "cash_invested": Decimal(str(row["cash_invested"])) if pd.notna(row.get("cash_invested")) else None,
            "current_market_value": Decimal(str(row["current_market_value"])) if pd.notna(row.get("current_market_value")) else None,
            "property_status": row.get("property_status", "evaluating"),
            "vacancy_rate": Decimal(str(row["vacancy_rate"])) if pd.notna(row.get("vacancy_rate")) else Decimal("0.07"),
            "monthly_rent_to_income_ratio": Decimal(str(row["monthly_rent_to_income_ratio"])) if pd.notna(row.get("monthly_rent_to_income_ratio")) else None,
            "address_line1": row.get("address_line1"),
            "address_line2": row.get("address_line2"),
            "city": row.get("city"),
            "state": row.get("state"),
            "zip_code": row.get("zip_code"),
            "property_type": row.get("property_type"),
            "bedrooms": int(row["bedrooms"]) if pd.notna(row.get("bedrooms")) else None,
            "bathrooms": Decimal(str(row["bathrooms"])) if pd.notna(row.get("bathrooms")) else None,
            "square_feet": int(row["square_feet"]) if pd.notna(row.get("square_feet")) else None,
            "year_built": int(row["year_built"]) if pd.notna(row.get("year_built")) else None,
            "current_monthly_rent": Decimal(str(row["current_monthly_rent"])) if pd.notna(row.get("current_monthly_rent")) else None,
            "notes": row.get("notes"),
            "is_active": bool(row["is_active"]) if pd.notna(row.get("is_active")) else True,
            "created_at": row["created_at"] if pd.notna(row.get("created_at")) else pd.Timestamp.now(),
            "updated_at": row["updated_at"] if pd.notna(row.get("updated_at")) else pd.Timestamp.now(),
        }
        
        return PropertyResponse(**prop_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property_endpoint(
    property_id: str,
    property_data: PropertyUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a property in Iceberg (checks ownership and sharing)"""
    try:
        user_id = current_user["sub"]  # Already a string
        user_email = current_user["email"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Read table and find property
        df = read_table(NAMESPACE, TABLE_NAME)
        property_rows = df[df["id"] == property_id]
        
        if len(property_rows) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_user_id = str(property_rows.iloc[0]["user_id"])
        
        # Check access: owner OR bidirectional share
        from app.api.sharing_utils import user_has_property_access
        if not user_has_property_access(property_user_id, user_id, user_email):
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Ensure all expected columns exist in DataFrame (for schema evolution)
        # Get the table schema to check for missing columns
        table = _load_properties_table()
        schema_fields = {field.name for field in table.schema().fields}
        # Only add columns that exist in the schema (don't add new columns that aren't in schema yet)
        for col in schema_fields:
            if col not in df.columns:
                df[col] = None
        # Remove any columns from DataFrame that don't exist in schema
        columns_to_remove = [col for col in df.columns if col not in schema_fields]
        if columns_to_remove:
            logger.warning(f"Removing columns from DataFrame that don't exist in table schema: {columns_to_remove}")
            df = df.drop(columns=columns_to_remove)
        
        # Update the property
        mask = df["id"] == property_id
        
        # Update fields
        update_dict = property_data.model_dump(exclude_none=True)
        logger.info(f"Update dict received: {update_dict}")
        
        for key, value in update_dict.items():
            logger.info(f"Processing key: {key}, in columns: {key in df.columns}")
            if key in df.columns:
                logger.info(f"Updating {key} with value {value} (type: {type(value)})")
                # Convert Decimal fields
                if key in ["purchase_price", "down_payment", "cash_invested", "current_market_value", "vacancy_rate", "monthly_rent_to_income_ratio", "bathrooms", "current_monthly_rent"]:
                    df.loc[mask, key] = Decimal(str(value)) if value is not None else None
                # Handle date fields
                elif key == "purchase_date":
                    df.loc[mask, key] = pd.to_datetime(value) if value is not None else None
                # Handle enum fields - convert to string
                elif key == "property_status":
                    status_value = str(value) if value is not None else "evaluating"
                    logger.info(f"Setting property_status to: {status_value}")
                    df.loc[mask, key] = status_value
                else:
                    df.loc[mask, key] = value
            else:
                logger.warning(f"Key {key} not found in dataframe columns")
        
        # Update timestamp
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Extract only the updated row
        updated_row_df = df[mask].copy().reset_index(drop=True)
        
        # CRITICAL: Ensure the updated row has ALL schema columns and required fields are non-null
        # This prevents schema mismatch errors during upsert
        table = _load_properties_table()
        schema_fields = {field.name for field in table.schema().fields}
        for col in schema_fields:
            if col not in updated_row_df.columns:
                updated_row_df[col] = None
        
        # Ensure required fields are present and non-null
        if pd.isna(updated_row_df.iloc[0]["id"]) or updated_row_df.iloc[0]["id"] is None:
            updated_row_df.iloc[0, updated_row_df.columns.get_loc("id")] = property_id
        if pd.isna(updated_row_df.iloc[0]["user_id"]) or updated_row_df.iloc[0]["user_id"] is None:
            updated_row_df.iloc[0, updated_row_df.columns.get_loc("user_id")] = property_user_id
        if pd.isna(updated_row_df.iloc[0]["purchase_price"]) or updated_row_df.iloc[0]["purchase_price"] is None:
            # Get purchase_price from existing row if not in update
            existing_price = property_rows.iloc[0].get("purchase_price")
            if pd.notna(existing_price):
                updated_row_df.iloc[0, updated_row_df.columns.get_loc("purchase_price")] = existing_price
        
        # Reorder columns to match schema order
        schema_column_order = [field.name for field in table.schema().fields]
        updated_row_df = updated_row_df[[col for col in schema_column_order if col in updated_row_df.columns]]
        
        # Check if vacancy rate or square feet changed - update vacancy expenses
        if "vacancy_rate" in update_dict or "square_feet" in update_dict:
            updated_row = df[mask].iloc[0]
            square_feet = int(updated_row["square_feet"]) if pd.notna(updated_row.get("square_feet")) else None
            vacancy_rate = Decimal(str(updated_row["vacancy_rate"])) if pd.notna(updated_row.get("vacancy_rate")) else Decimal("0.07")
            
            if square_feet and square_feet > 0:
                logger.info(f"Updating vacancy expenses: SF={square_feet}, vacancy_rate={vacancy_rate}")
                await create_or_update_vacancy_expenses(
                    property_id=property_id,
                    square_feet=square_feet,
                    vacancy_rate=vacancy_rate
                )
        
        # Check if current_market_value changed - update tax savings
        if "current_market_value" in update_dict:
            updated_row = df[mask].iloc[0]
            current_market_value = updated_row.get("current_market_value")
            if pd.notna(current_market_value):
                current_market_value = Decimal(str(current_market_value))
                purchase_date = updated_row.get("purchase_date")
                if pd.notna(purchase_date):
                    purchase_date = purchase_date.date() if hasattr(purchase_date, 'date') else purchase_date
                else:
                    purchase_date = None
                
                logger.info(f"Updating tax savings: current_market_value=${current_market_value}")
                await create_or_update_tax_savings(
                    property_id=property_id,
                    user_id=user_id,
                    current_market_value=current_market_value,
                    purchase_date=purchase_date
                )
        
        # Property-specific upsert - build ordered dict in exact schema order
        table = _load_properties_table()
        table_schema = table.schema().as_arrow()
        schema_field_names = [field.name for field in table_schema]
        
        # Build ordered dict ensuring required fields are non-null
        ordered_dict = {}
        for field_name in schema_field_names:
            if field_name == "id":
                ordered_dict[field_name] = str(property_id)  # Required
            elif field_name == "user_id":
                ordered_dict[field_name] = str(property_user_id)  # Required
            elif field_name == "purchase_price":
                # Required - get from update or existing
                value = updated_row_df.iloc[0].get(field_name) if field_name in updated_row_df.columns else property_rows.iloc[0].get(field_name)
                ordered_dict[field_name] = int(value) if pd.notna(value) else int(property_rows.iloc[0].get(field_name))
            else:
                # Get value from updated_row_df or existing row
                value = updated_row_df.iloc[0].get(field_name) if field_name in updated_row_df.columns else property_rows.iloc[0].get(field_name)
                ordered_dict[field_name] = value
        
        # Create DataFrame and convert to PyArrow
        property_df = pd.DataFrame([ordered_dict])
        import pyarrow as pa
        arrow_table = pa.Table.from_pandas(property_df, preserve_index=False)
        arrow_table = arrow_table.cast(table_schema)
        
        # Perform upsert
        table.upsert(arrow_table, join_cols=["id"])
        
        # Get updated property from the ordered dict
        updated_row = ordered_dict
        logger.info(f"Updated row property_status: {updated_row.get('property_status')}")
        
        # Convert to response
        prop_dict = {
            "id": UUID(str(updated_row["id"])),
            "user_id": UUID(str(updated_row["user_id"])),
            "display_name": updated_row.get("display_name"),
            "purchase_price": Decimal(str(updated_row["purchase_price"])),
            "down_payment": Decimal(str(updated_row["down_payment"])) if pd.notna(updated_row.get("down_payment")) else None,
            "cash_invested": Decimal(str(updated_row["cash_invested"])) if "cash_invested" in updated_row and pd.notna(updated_row.get("cash_invested")) else None,
            "current_market_value": Decimal(str(updated_row["current_market_value"])) if pd.notna(updated_row.get("current_market_value")) else None,
            "property_status": updated_row.get("property_status", "evaluating"),
            "vacancy_rate": Decimal(str(updated_row["vacancy_rate"])) if pd.notna(updated_row.get("vacancy_rate")) else Decimal("0.07"),
            "monthly_rent_to_income_ratio": Decimal(str(updated_row["monthly_rent_to_income_ratio"])) if pd.notna(updated_row.get("monthly_rent_to_income_ratio")) else None,
            "address_line1": updated_row.get("address_line1"),
            "address_line2": updated_row.get("address_line2"),
            "city": updated_row.get("city"),
            "state": updated_row.get("state"),
            "zip_code": updated_row.get("zip_code"),
            "property_type": updated_row.get("property_type"),
            "bedrooms": int(updated_row["bedrooms"]) if pd.notna(updated_row.get("bedrooms")) else None,
            "bathrooms": Decimal(str(updated_row["bathrooms"])) if pd.notna(updated_row.get("bathrooms")) else None,
            "square_feet": int(updated_row["square_feet"]) if pd.notna(updated_row.get("square_feet")) else None,
            "year_built": int(updated_row["year_built"]) if pd.notna(updated_row.get("year_built")) else None,
            "current_monthly_rent": Decimal(str(updated_row["current_monthly_rent"])) if pd.notna(updated_row.get("current_monthly_rent")) else None,
            "notes": updated_row.get("notes"),
            "is_active": bool(updated_row["is_active"]) if pd.notna(updated_row.get("is_active")) else True,
            "created_at": updated_row["created_at"] if pd.notna(updated_row.get("created_at")) else pd.Timestamp.now(),
            "updated_at": updated_row["updated_at"] if pd.notna(updated_row.get("updated_at")) else pd.Timestamp.now(),
        }
        
        return PropertyResponse(**prop_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{property_id}", status_code=204)
async def delete_property_endpoint(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a property (hard delete) in Iceberg - OWNER ONLY"""
    try:
        user_id = current_user["sub"]  # Already a string
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Property not found")
        
        # OPTIMIZATION: Use filtered read instead of reading entire table
        # Verify property exists and user is the OWNER (not just shared access)
        property_df = read_table_filtered(
            NAMESPACE,
            TABLE_NAME,
            EqualTo("id", property_id),
            selected_columns=["id", "user_id", "is_active"]
        )
        
        if len(property_df) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_row = property_df.iloc[0]
        property_user_id = str(property_row["user_id"])
        is_active = bool(property_row["is_active"]) if pd.notna(property_row.get("is_active")) else True
        
        # Verify ownership (only owners can delete, not shared users)
        if property_user_id != user_id:
            raise HTTPException(status_code=404, detail="Property not found or you don't have permission to delete")
        
        # Verify property is active
        if not is_active:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Get fresh table reference for writes to avoid lock issues
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, TABLE_NAME)
        table = catalog.load_table(table_identifier)
        
        # HARD DELETE: Permanently remove the property using Iceberg's delete API
        logger.info(f"🗑️ [PROPERTY] Hard deleting property {property_id} by user {user_id}")
        table.delete(EqualTo("id", property_id))
        
        logger.info(f"✅ Property {property_id} permanently deleted by user {user_id}")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
