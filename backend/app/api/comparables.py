"""
Rental Comparables API endpoints
"""
import uuid
import logging
from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import pandas as pd
import pyarrow as pa

from app.core.dependencies import get_current_user
from app.core.iceberg import get_catalog, read_table, table_exists, load_table, append_data
from app.schemas.comparable import (
    ComparableCreate,
    ComparableUpdate,
    ComparableResponse,
    ComparableListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comparables", tags=["comparables"])

NAMESPACE = ("investflow",)
TABLE_NAME = "rental_comparables"


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
        pa.field("garage_spaces", pa.float32(), nullable=True),
        # Listing data
        pa.field("date_listed", pa.date32(), nullable=False),
        pa.field("contacts", pa.int32(), nullable=True),
        # Rental status
        pa.field("is_rented", pa.bool_(), nullable=True),
        pa.field("last_rented_price", pa.decimal128(10, 2), nullable=True),
        pa.field("last_rented_year", pa.int32(), nullable=True),
        # Flags
        pa.field("is_subject_property", pa.bool_(), nullable=False),
        pa.field("is_active", pa.bool_(), nullable=False),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


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
    
    # Days on Zillow
    date_listed = row.get('date_listed')
    if date_listed:
        if isinstance(date_listed, str):
            date_listed = datetime.fromisoformat(date_listed).date()
        days_on_zillow = (today - date_listed).days
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
        
        # Create comparable record
        comparable_id = str(uuid.uuid4())
        now = pd.Timestamp.now(tz=timezone.utc).floor('us')
        
        comparable_dict = {
            "id": comparable_id,
            "property_id": comparable_data.property_id,
            "unit_id": comparable_data.unit_id,
            "address": comparable_data.address,
            "city": comparable_data.city,
            "state": comparable_data.state,
            "zip_code": comparable_data.zip_code,
            "property_type": comparable_data.property_type,
            "is_furnished": comparable_data.is_furnished,
            "bedrooms": comparable_data.bedrooms,
            "bathrooms": float(comparable_data.bathrooms),
            "square_feet": comparable_data.square_feet,
            "asking_price": float(comparable_data.asking_price),
            "has_fence": comparable_data.has_fence,
            "has_solid_flooring": comparable_data.has_solid_flooring,
            "has_quartz_granite": comparable_data.has_quartz_granite,
            "has_ss_appliances": comparable_data.has_ss_appliances,
            "has_shaker_cabinets": comparable_data.has_shaker_cabinets,
            "has_washer_dryer": comparable_data.has_washer_dryer,
            "garage_spaces": comparable_data.garage_spaces,
            "date_listed": comparable_data.date_listed,
            "contacts": comparable_data.contacts,
            "is_rented": comparable_data.is_rented,
            "last_rented_price": float(comparable_data.last_rented_price) if comparable_data.last_rented_price else None,
            "last_rented_year": comparable_data.last_rented_year,
            "is_subject_property": comparable_data.is_subject_property,
            "is_active": True,
            "notes": comparable_data.notes,
            "created_at": now,
            "updated_at": now,
        }
        
        # Convert to DataFrame and append
        df = pd.DataFrame([comparable_dict])
        append_data(NAMESPACE, TABLE_NAME, df)
        
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
        
        # Update fields
        update_data = comparable_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            df.loc[comp_idx[0], field] = value
        
        # Update timestamp
        df.loc[comp_idx[0], 'updated_at'] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)
        
        # Convert decimal columns to float64 for PyArrow compatibility
        decimal_cols = ['bathrooms', 'asking_price', 'last_rented_price']
        for col in decimal_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convert timestamps
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None).dt.floor('us')
        
        # Convert to PyArrow and overwrite
        arrow_table = pa.Table.from_pandas(df)
        arrow_table = arrow_table.cast(table.schema().as_arrow())
        table.overwrite(arrow_table)
        
        logger.info(f"✅ Comparable updated: {comparable_id}")
        
        # Return updated comparable
        updated_row = df.loc[comp_idx[0]].to_dict()
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
            # Remove the row
            df = df.drop(comp_idx[0])
        else:
            # Soft delete
            df.loc[comp_idx[0], 'is_active'] = False
            df.loc[comp_idx[0], 'updated_at'] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)
        
        # Convert decimal columns to float64
        decimal_cols = ['bathrooms', 'asking_price', 'last_rented_price']
        for col in decimal_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convert timestamps
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None).dt.floor('us')
        
        # Overwrite table
        arrow_table = pa.Table.from_pandas(df)
        arrow_table = arrow_table.cast(table.schema().as_arrow())
        table.overwrite(arrow_table)
        
        logger.info(f"✅ Comparable {'deleted' if hard_delete else 'deactivated'}: {comparable_id}")
        
        return {"message": f"Comparable {'deleted' if hard_delete else 'deactivated'} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting comparable: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


