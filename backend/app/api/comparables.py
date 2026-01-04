"""
Rental Comparables API endpoints
"""
import uuid
import logging
from datetime import datetime, date, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import pandas as pd
import pyarrow as pa

from app.core.dependencies import get_current_user
from app.core.iceberg import get_catalog, read_table, table_exists, load_table, append_data, upsert_data
from app.schemas.comparable import (
    ComparableCreate,
    ComparableUpdate,
    ComparableResponse,
    ComparableListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comparables", tags=["comparables"])

NAMESPACE = ("investflow",)
TABLE_NAME = "comps"  # Comparable property data is stored in comps table

# Strict field order for comps table (must match Iceberg schema exactly)
# Order from get_comparable_schema():
COMPS_FIELD_ORDER = [
    "id",
    "property_id",
    "unit_id",
    "address",
    "city",
    "state",
    "zip_code",
    "property_type",
    "is_furnished",
    "bedrooms",
    "bathrooms",
    "square_feet",
    "asking_price",
    "has_fence",
    "has_solid_flooring",
    "has_quartz_granite",
    "has_ss_appliances",
    "has_shaker_cabinets",
    "has_washer_dryer",
    "garage_spaces",
    "date_listed",
    "date_rented",
    "contacts",
    "is_rented",
    "last_rented_price",
    "last_rented_year",
    "is_subject_property",
    "is_active",
    "notes",
    "created_at",
    "updated_at",
]


def get_comparable_schema() -> pa.Schema:
    """Create PyArrow schema for rental_comparables table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("unit_id", pa.string(), nullable=True),
        pa.field("address", pa.string(), nullable=False),
        pa.field("city", pa.string(), nullable=True),
        pa.field("state", pa.string(), nullable=True),
        pa.field("zip_code", pa.string(), nullable=True),
        # Property classification
        pa.field("property_type", pa.string(), nullable=True),  # House, Duplex, Townhouse, etc.
        pa.field("is_furnished", pa.bool_(), nullable=True),
        # Property details
        pa.field("bedrooms", pa.int32(), nullable=False),
        pa.field("bathrooms", pa.decimal128(3, 1), nullable=False),
        pa.field("square_feet", pa.int32(), nullable=False),
        pa.field("asking_price", pa.decimal128(10, 2), nullable=False),
        # Amenities
        pa.field("has_fence", pa.bool_(), nullable=True),
        pa.field("has_solid_flooring", pa.bool_(), nullable=True),
        pa.field("has_quartz_granite", pa.bool_(), nullable=True),
        pa.field("has_ss_appliances", pa.bool_(), nullable=True),
        pa.field("has_shaker_cabinets", pa.bool_(), nullable=True),
        pa.field("has_washer_dryer", pa.bool_(), nullable=True),
        pa.field("garage_spaces", pa.decimal128(3, 1), nullable=True),  # Supports .5 increments (0.5, 1.0, 1.5, etc.)
        # Listing data
        pa.field("date_listed", pa.date32(), nullable=False),
        pa.field("date_rented", pa.date32(), nullable=True),  # Date property was rented (for accurate DOZ)
        pa.field("contacts", pa.int32(), nullable=True),  # Inquiries/contacts (null if is_rented = true, since not visible on Zillow)
        # Rental status
        pa.field("is_rented", pa.bool_(), nullable=True),  # True if rented (no longer listed) - contacts must be null
        pa.field("last_rented_price", pa.decimal128(10, 2), nullable=True),
        pa.field("last_rented_year", pa.int32(), nullable=True),
        # Flags
        pa.field("is_subject_property", pa.bool_(), nullable=False),
        pa.field("is_active", pa.bool_(), nullable=False),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


def _load_comps_table():
    """Load comps table (dedicated function, no shared functions)"""
    catalog = get_catalog()
    return catalog.load_table(f"{NAMESPACE[0]}.{TABLE_NAME}")


def _convert_comparable_types(df: pd.DataFrame, table_schema) -> pd.DataFrame:
    """Convert DataFrame types to match table schema (dedicated function, no shared functions)"""
    # Get actual table schema field order
    actual_field_order = [f.name for f in table_schema]
    
    # Ensure DataFrame columns are in exact order matching table schema
    df = df[actual_field_order]
    
    # Convert timestamp columns to microseconds
    for col in ['created_at', 'updated_at']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
            df[col] = df[col].dt.floor('us')
    
    # Convert date columns
    for col in ['date_listed', 'date_rented']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    
    # Convert decimal columns to proper types
    if 'bathrooms' in df.columns:
        df['bathrooms'] = df['bathrooms'].apply(
            lambda x: Decimal(str(round(float(x), 1))) if pd.notna(x) else Decimal('0')
        )
    if 'asking_price' in df.columns:
        df['asking_price'] = df['asking_price'].apply(
            lambda x: Decimal(str(round(float(x), 2))) if pd.notna(x) else Decimal('0')
        )
    if 'last_rented_price' in df.columns:
        df['last_rented_price'] = df['last_rented_price'].apply(
            lambda x: Decimal(str(round(float(x), 2))) if pd.notna(x) else None
        )
    if 'garage_spaces' in df.columns:
        df['garage_spaces'] = df['garage_spaces'].apply(
            lambda x: Decimal(str(round(float(x), 1))) if pd.notna(x) and x is not None else None
        )
    
    # Convert integer columns
    int_cols = ['bedrooms', 'square_feet', 'contacts', 'last_rented_year']
    for col in int_cols:
        if col in df.columns:
            if col in ['bedrooms', 'square_feet']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    
    # Convert boolean columns
    bool_cols = ['is_subject_property', 'is_active', 'is_furnished', 'has_fence', 
                 'has_solid_flooring', 'has_quartz_granite', 'has_ss_appliances',
                 'has_shaker_cabinets', 'has_washer_dryer', 'is_rented']
    for col in bool_cols:
        if col in df.columns:
            if col in ['is_subject_property', 'is_active']:
                df[col] = df[col].fillna(False).astype(bool)
            else:
                df[col] = df[col].astype('boolean')
    
    # Convert string columns
    string_cols = ['id', 'property_id', 'address']
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].astype(str)
            df[col] = df[col].fillna('')
    
    return df


def _append_comparable(comparable_dict: dict):
    """Append a comparable with strict field ordering (dedicated function, no shared functions)"""
    try:
        table = _load_comps_table()
        table_schema = table.schema().as_arrow()
        
        # Get actual table schema field order
        actual_field_order = [f.name for f in table_schema]
        logger.info(f"📋 [COMPS] Actual table schema order: {actual_field_order}")
        logger.info(f"📋 [COMPS] Expected field order: {COMPS_FIELD_ORDER}")
        logger.info(f"📋 [COMPS] Comparable dict keys: {list(comparable_dict.keys())}")
        
        # Build DataFrame with fields in exact order matching ACTUAL table schema
        ordered_dict = {}
        for field_name in actual_field_order:
            if field_name in comparable_dict:
                ordered_dict[field_name] = comparable_dict[field_name]
            else:
                ordered_dict[field_name] = None
        
        df = pd.DataFrame([ordered_dict])
        df = _convert_comparable_types(df, table_schema)
        
        # Convert to PyArrow and cast to schema
        arrow_table = pa.Table.from_pandas(df)
        arrow_table = arrow_table.cast(table_schema)
        table.append(arrow_table)
        
        logger.info(f"✅ [COMPS] Appended comparable: {comparable_dict.get('id')}")
        
    except Exception as e:
        logger.error(f"❌ [COMPS] Failed to append comparable: {e}", exc_info=True)
        raise


def _overwrite_comps_table(df: pd.DataFrame):
    """Overwrite comps table with DataFrame (dedicated function, no shared functions)"""
    try:
        table = _load_comps_table()
        table_schema = table.schema().as_arrow()
        
        # Get actual table schema field order
        actual_field_order = [f.name for f in table_schema]
        
        # Ensure DataFrame has all required columns in correct order
        for field_name in actual_field_order:
            if field_name not in df.columns:
                df[field_name] = None
        
        df = df[actual_field_order]
        df = _convert_comparable_types(df, table_schema)
        
        # Convert to PyArrow and cast to schema
        arrow_table = pa.Table.from_pandas(df)
        arrow_table = arrow_table.cast(table_schema)
        
        # Overwrite table
        table.overwrite(arrow_table)
        
        logger.info(f"✅ [COMPS] Overwrote comps table with {len(df)} rows")
        
    except Exception as e:
        logger.error(f"❌ [COMPS] Failed to overwrite comps table: {e}", exc_info=True)
        raise


def ensure_table_exists():
    """Create rental_comparables table if it doesn't exist"""
    if not table_exists(NAMESPACE, TABLE_NAME):
        logger.info(f"Creating {TABLE_NAME} table")
        catalog = get_catalog()
        schema = get_comparable_schema()
        catalog.create_table(
            identifier=f"{NAMESPACE[0]}.{TABLE_NAME}",
            schema=schema
        )
        logger.info(f"✅ Created {TABLE_NAME} table")


def calculate_computed_fields(row: dict) -> dict:
    """Calculate computed fields for a comparable"""
    today = date.today()
    
    # Days on Zillow - use date_rented only if property is actually rented, otherwise use today
    date_rented = row.get('date_rented')
    date_listed = row.get('date_listed')
    is_rented = row.get('is_rented')
    
    # DOZ = (date_rented - date_listed) if rented, otherwise (today - date_listed)
    if date_listed:
        # Convert date_listed to date object if needed
        if isinstance(date_listed, str):
            date_listed_date = datetime.fromisoformat(date_listed).date()
        elif isinstance(date_listed, pd.Timestamp):
            date_listed_date = date_listed.date()
        else:
            date_listed_date = date_listed
        
        # Only use date_rented if property is actually rented
        if is_rented is True and date_rented:
            # Property was rented - use date_rented as end date
            if isinstance(date_rented, str):
                date_rented_date = datetime.fromisoformat(date_rented).date()
            elif isinstance(date_rented, pd.Timestamp):
                date_rented_date = date_rented.date()
            else:
                date_rented_date = date_rented
            days_on_zillow = (date_rented_date - date_listed_date).days
        else:
            # Property not rented yet - use today as end date
            days_on_zillow = (today - date_listed_date).days
        
        row['days_on_zillow'] = max(1, days_on_zillow)  # At least 1 day
    else:
        row['days_on_zillow'] = None
    
    # Price per SF
    square_feet = row.get('square_feet')
    asking_price = row.get('asking_price')
    if square_feet and asking_price and square_feet > 0:
        row['price_per_sf'] = round(float(asking_price) / float(square_feet), 2)
    else:
        row['price_per_sf'] = None
    
    # Contact Rate (CR)
    # If property is rented (not listed), contacts are not visible, so CR must be None
    is_rented = row.get('is_rented')
    if is_rented is True:
        row['contact_rate'] = None
    else:
        contacts = row.get('contacts')
        if contacts is not None and row.get('days_on_zillow'):
            row['contact_rate'] = round(float(contacts) / float(row['days_on_zillow']), 2)
        else:
            row['contact_rate'] = None
    
    # Actual Price per SF (ACT $-SF)
    last_rented_price = row.get('last_rented_price')
    if last_rented_price and float(last_rented_price) > 0 and square_feet and square_feet > 0:
        row['actual_price_per_sf'] = round(float(last_rented_price) / float(square_feet), 2)
    else:
        row['actual_price_per_sf'] = None
    
    return row


@router.get("", response_model=ComparableListResponse)
async def list_comparables(
    property_id: str = Query(..., description="Property ID to get comparables for"),
    unit_id: Optional[str] = Query(None, description="Optional unit ID for multi-unit properties"),
    include_inactive: bool = Query(False, description="Include inactive comparables"),
    current_user: dict = Depends(get_current_user)
):
    """List all comparables for a property/unit"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Fetching comparables for property {property_id}")
        
        ensure_table_exists()
        
        # Verify property belongs to user
        properties_df = read_table(NAMESPACE, "properties")
        if properties_df is None or properties_df.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Get comparables
        if not table_exists(NAMESPACE, TABLE_NAME):
            return ComparableListResponse(items=[], total=0)
        
        df = read_table(NAMESPACE, TABLE_NAME)
        
        if df is None or df.empty:
            return ComparableListResponse(items=[], total=0)
        
        # Filter by property
        df = df[df['property_id'] == property_id]
        
        # Deduplicate: keep only the latest version of each comparable (by id)
        # Sort by updated_at descending and drop duplicates keeping first (most recent)
        if len(df) > 0 and 'updated_at' in df.columns:
            df = df.sort_values('updated_at', ascending=False)
            df = df.drop_duplicates(subset=['id'], keep='first')
        
        # Filter by unit if specified
        if unit_id:
            df = df[(df['unit_id'] == unit_id) | (df['unit_id'].isna())]
        
        # Filter inactive unless requested
        if not include_inactive:
            df = df[df['is_active'] == True]
        
        # Calculate computed fields first (need actual_price_per_sf for sorting)
        items = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            # Replace NaN with None
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row_dict.items()}
            # Calculate computed fields
            row_dict = calculate_computed_fields(row_dict)
            items.append(row_dict)
        
        # Sort by:
        # 1. Subject property first (True sorts before False with descending)
        # 2. Highest actual_price_per_sf (if available)
        # 3. Highest price_per_sf
        # 4. Least amenities to most (ascending amenity count)
        def sort_key(item):
            # Count amenities (True = 1, False/None = 0)
            amenity_count = sum([
                1 if item.get('has_fence') else 0,
                1 if item.get('has_solid_flooring') else 0,
                1 if item.get('has_quartz_granite') else 0,
                1 if item.get('has_ss_appliances') else 0,
                1 if item.get('has_shaker_cabinets') else 0,
                1 if item.get('has_washer_dryer') else 0,
            ])
            
            return (
                0 if item.get('is_subject_property') else 1,  # Subject first
                -(item.get('actual_price_per_sf') or -999),     # Highest actual $/SF (negative for descending)
                -(item.get('price_per_sf') or -999),            # Highest $/SF
                amenity_count,                                   # Least amenities first (ascending)
            )
        
        items.sort(key=sort_key)
        
        return ComparableListResponse(items=[ComparableResponse(**item) for item in items], total=len(items))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching comparables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ComparableResponse)
async def create_comparable(
    comparable_data: ComparableCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new comparable"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Creating comparable for property {comparable_data.property_id}")
        
        ensure_table_exists()
        
        # Verify property belongs to user
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == comparable_data.property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Create comparable record in EXACT field order
        comparable_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        logger.info(f"📋 [COMPS] Creating comparable with field order: {COMPS_FIELD_ORDER}")
        
        # Convert date_listed to date object
        date_listed = comparable_data.date_listed.date() if hasattr(comparable_data.date_listed, 'date') else comparable_data.date_listed
        
        # Default date_rented to date_listed + 30 days if not provided
        if comparable_data.date_rented:
            date_rented = comparable_data.date_rented.date() if hasattr(comparable_data.date_rented, 'date') else comparable_data.date_rented
        else:
            from datetime import timedelta
            date_rented = date_listed + timedelta(days=30) if date_listed else None
        
        # Build comparable_dict in EXACT field order matching COMPS_FIELD_ORDER
        from decimal import Decimal
        comparable_dict = {}
        for field_name in COMPS_FIELD_ORDER:
            if field_name == "id":
                comparable_dict[field_name] = comparable_id
            elif field_name == "property_id":
                comparable_dict[field_name] = str(comparable_data.property_id)
            elif field_name == "unit_id":
                comparable_dict[field_name] = str(comparable_data.unit_id) if comparable_data.unit_id else None
            elif field_name == "address":
                comparable_dict[field_name] = comparable_data.address
            elif field_name == "city":
                comparable_dict[field_name] = comparable_data.city
            elif field_name == "state":
                comparable_dict[field_name] = comparable_data.state
            elif field_name == "zip_code":
                comparable_dict[field_name] = comparable_data.zip_code
            elif field_name == "property_type":
                comparable_dict[field_name] = comparable_data.property_type
            elif field_name == "is_furnished":
                comparable_dict[field_name] = comparable_data.is_furnished
            elif field_name == "bedrooms":
                comparable_dict[field_name] = comparable_data.bedrooms
            elif field_name == "bathrooms":
                comparable_dict[field_name] = Decimal(str(comparable_data.bathrooms))
            elif field_name == "square_feet":
                comparable_dict[field_name] = comparable_data.square_feet
            elif field_name == "asking_price":
                comparable_dict[field_name] = Decimal(str(comparable_data.asking_price))
            elif field_name == "has_fence":
                comparable_dict[field_name] = comparable_data.has_fence
            elif field_name == "has_solid_flooring":
                comparable_dict[field_name] = comparable_data.has_solid_flooring
            elif field_name == "has_quartz_granite":
                comparable_dict[field_name] = comparable_data.has_quartz_granite
            elif field_name == "has_ss_appliances":
                comparable_dict[field_name] = comparable_data.has_ss_appliances
            elif field_name == "has_shaker_cabinets":
                comparable_dict[field_name] = comparable_data.has_shaker_cabinets
            elif field_name == "has_washer_dryer":
                comparable_dict[field_name] = comparable_data.has_washer_dryer
            elif field_name == "garage_spaces":
                comparable_dict[field_name] = Decimal(str(round(float(comparable_data.garage_spaces or 0), 1))) if comparable_data.garage_spaces is not None else None
            elif field_name == "date_listed":
                comparable_dict[field_name] = date_listed
            elif field_name == "date_rented":
                comparable_dict[field_name] = date_rented
            elif field_name == "contacts":
                comparable_dict[field_name] = None if comparable_data.is_rented else comparable_data.contacts
            elif field_name == "is_rented":
                comparable_dict[field_name] = comparable_data.is_rented
            elif field_name == "last_rented_price":
                comparable_dict[field_name] = Decimal(str(comparable_data.last_rented_price)) if comparable_data.last_rented_price else None
            elif field_name == "last_rented_year":
                comparable_dict[field_name] = comparable_data.last_rented_year
            elif field_name == "is_subject_property":
                comparable_dict[field_name] = comparable_data.is_subject_property
            elif field_name == "is_active":
                comparable_dict[field_name] = True
            elif field_name == "notes":
                comparable_dict[field_name] = comparable_data.notes
            elif field_name == "created_at":
                comparable_dict[field_name] = now
            elif field_name == "updated_at":
                comparable_dict[field_name] = now
        
        # Append using dedicated function (respects field order)
        _append_comparable(comparable_dict)
        
        logger.info(f"✅ Comparable created: {comparable_id}")
        
        # Calculate computed fields and return
        comparable_dict = calculate_computed_fields(comparable_dict)
        return ComparableResponse(**comparable_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating comparable: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{comparable_id}", response_model=ComparableResponse)
async def update_comparable(
    comparable_id: str,
    comparable_update: ComparableUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a comparable"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Updating comparable {comparable_id}")
        
        # Read all comparables
        table = load_table(NAMESPACE, TABLE_NAME)
        df = read_table(NAMESPACE, TABLE_NAME)
        
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="Comparable not found")
        
        # Find the comparable
        comp_idx = df[df['id'] == comparable_id].index
        if comp_idx.empty:
            raise HTTPException(status_code=404, detail="Comparable not found")
        
        # Verify property belongs to user
        property_id = df.loc[comp_idx[0], 'property_id']
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Get the row to update and convert to dict
        updated_row = df.loc[comp_idx[0]].to_dict()
        
        # Convert date fields from pandas Timestamp to date objects
        for date_field in ['date_listed', 'date_rented']:
            if date_field in updated_row and pd.notna(updated_row[date_field]):
                if isinstance(updated_row[date_field], pd.Timestamp):
                    updated_row[date_field] = updated_row[date_field].date()
                elif hasattr(updated_row[date_field], 'date'):
                    updated_row[date_field] = updated_row[date_field].date()
            elif date_field in updated_row:
                updated_row[date_field] = None
        
        # Update fields from the update request
        update_data = comparable_update.model_dump(exclude_unset=True)
        
        # If is_rented is being set to true (or already true), contacts must be null (not visible on Zillow)
        final_is_rented = update_data.get('is_rented') if 'is_rented' in update_data else updated_row.get('is_rented')
        if final_is_rented is True:
            update_data['contacts'] = None
        
        # Handle date_listed conversion if it's being updated
        if 'date_listed' in update_data and update_data['date_listed']:
            if isinstance(update_data['date_listed'], str):
                update_data['date_listed'] = datetime.strptime(update_data['date_listed'], "%Y-%m-%d").date()
            elif hasattr(update_data['date_listed'], 'date'):
                update_data['date_listed'] = update_data['date_listed'].date()
        
        # Handle date_rented conversion if it's being updated
        if 'date_rented' in update_data:
            if update_data['date_rented']:
                if isinstance(update_data['date_rented'], str):
                    update_data['date_rented'] = datetime.strptime(update_data['date_rented'], "%Y-%m-%d").date()
                elif hasattr(update_data['date_rented'], 'date'):
                    update_data['date_rented'] = update_data['date_rented'].date()
            else:
                update_data['date_rented'] = None
        
        # Update the row
        updated_row.update(update_data)
        updated_row['updated_at'] = datetime.utcnow()
        
        # Convert decimal fields properly
        if 'garage_spaces' in update_data and update_data['garage_spaces'] is not None:
            updated_row['garage_spaces'] = Decimal(str(round(float(update_data['garage_spaces']), 1)))
        if 'bathrooms' in update_data:
            updated_row['bathrooms'] = Decimal(str(round(float(update_data['bathrooms']), 1)))
        if 'asking_price' in update_data:
            updated_row['asking_price'] = Decimal(str(round(float(update_data['asking_price']), 2)))
        if 'last_rented_price' in update_data and update_data['last_rented_price'] is not None:
            updated_row['last_rented_price'] = Decimal(str(round(float(update_data['last_rented_price']), 2)))
        
        # Build updated row in EXACT field order
        table = _load_comps_table()
        table_schema = table.schema().as_arrow()
        actual_field_order = [f.name for f in table_schema]
        
        ordered_dict = {}
        for field_name in actual_field_order:
            if field_name in updated_row:
                ordered_dict[field_name] = updated_row[field_name]
            else:
                ordered_dict[field_name] = None
        
        # Convert to DataFrame (single row) in exact order
        updated_df = pd.DataFrame([ordered_dict])
        updated_df = updated_df[actual_field_order]
        updated_df = _convert_comparable_types(updated_df, table_schema)
        
        # Read all data, update the row, and overwrite
        all_df = read_table(NAMESPACE, TABLE_NAME)
        all_df = all_df[all_df['id'] != comparable_id]  # Remove old row
        all_df = pd.concat([all_df, updated_df], ignore_index=True)  # Add updated row
        
        # Overwrite using dedicated function (respects field order)
        _overwrite_comps_table(all_df)
        
        logger.info(f"✅ Comparable updated: {comparable_id}")
        
        # Return updated comparable - convert DataFrame row to dict
        updated_row = updated_df.iloc[0].to_dict()
        updated_row = {k: (None if pd.isna(v) else v) for k, v in updated_row.items()}
        updated_row = calculate_computed_fields(updated_row)
        
        return ComparableResponse(**updated_row)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating comparable: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{comparable_id}")
async def delete_comparable(
    comparable_id: str,
    hard_delete: bool = Query(False, description="Permanently delete instead of soft delete"),
    current_user: dict = Depends(get_current_user)
):
    """Delete a comparable (soft delete by default)"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Deleting comparable {comparable_id}")
        
        table = load_table(NAMESPACE, TABLE_NAME)
        df = read_table(NAMESPACE, TABLE_NAME)
        
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="Comparable not found")
        
        # Find the comparable
        comp_idx = df[df['id'] == comparable_id].index
        if comp_idx.empty:
            raise HTTPException(status_code=404, detail="Comparable not found")
        
        # Verify property belongs to user
        property_id = df.loc[comp_idx[0], 'property_id']
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        if hard_delete:
            # Hard delete using PyIceberg delete API
            from pyiceberg.expressions import EqualTo
            table.delete(EqualTo("id", comparable_id))
        else:
            # Soft delete - update is_active and overwrite table
            updated_row = df.loc[comp_idx[0]].copy()
            updated_row['is_active'] = False
            updated_row['updated_at'] = datetime.utcnow()
            
            # Build updated row in EXACT field order
            table = _load_comps_table()
            table_schema = table.schema().as_arrow()
            actual_field_order = [f.name for f in table_schema]
            
            ordered_dict = {}
            for field_name in actual_field_order:
                if field_name in updated_row:
                    ordered_dict[field_name] = updated_row[field_name]
                else:
                    ordered_dict[field_name] = None
            
            # Convert to DataFrame and update
            updated_df = pd.DataFrame([ordered_dict])
            updated_df = updated_df[actual_field_order]
            updated_df = _convert_comparable_types(updated_df, table_schema)
            
            # Read all data, update the row, and overwrite
            all_df = read_table(NAMESPACE, TABLE_NAME)
            all_df = all_df[all_df['id'] != comparable_id]  # Remove old row
            all_df = pd.concat([all_df, updated_df], ignore_index=True)  # Add updated row
            
            # Overwrite using dedicated function (respects field order)
            _overwrite_comps_table(all_df)
        
        logger.info(f"✅ Comparable {'deleted' if hard_delete else 'deactivated'}: {comparable_id}")
        
        return {"message": f"Comparable {'deleted' if hard_delete else 'deactivated'} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting comparable: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


