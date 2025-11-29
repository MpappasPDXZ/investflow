"""API routes for unit management (multi-family/duplex properties)"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
import uuid
import pandas as pd
from decimal import Decimal

from app.core.dependencies import get_current_user
from app.schemas.unit import UnitCreate, UnitUpdate, UnitResponse, UnitListResponse
from app.core.iceberg import read_table, append_data, table_exists, load_table
from app.core.logging import get_logger

NAMESPACE = ("investflow",)
TABLE_NAME = "units"
PROPERTIES_TABLE = "properties"

router = APIRouter(prefix="/units", tags=["units"])
logger = get_logger(__name__)


@router.post("", response_model=UnitResponse, status_code=201)
async def create_unit_endpoint(
    unit_data: UnitCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new unit for a multi-family/duplex property"""
    try:
        user_id = current_user["sub"]
        
        # Verify property exists and belongs to user
        if not table_exists(NAMESPACE, PROPERTIES_TABLE):
            raise HTTPException(status_code=404, detail="Property not found")
        
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        property_row = properties_df[
            (properties_df["id"] == unit_data.property_id) & 
            (properties_df["user_id"] == user_id)
        ]
        
        if len(property_row) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Create unit
        unit_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        unit_dict = {
            "id": unit_id,
            "property_id": unit_data.property_id,
            "unit_number": unit_data.unit_number,
            "bedrooms": unit_data.bedrooms,
            "bathrooms": Decimal(str(unit_data.bathrooms)) if unit_data.bathrooms else None,
            "square_feet": unit_data.square_feet,
            "current_monthly_rent": Decimal(str(unit_data.current_monthly_rent)) if unit_data.current_monthly_rent else None,
            "notes": unit_data.notes,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
        }
        
        # Append to Iceberg table
        df = pd.DataFrame([unit_dict])
        append_data(NAMESPACE, TABLE_NAME, df)
        
        return UnitResponse(**unit_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating unit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=UnitListResponse)
async def list_units_endpoint(
    property_id: str = Query(..., description="Property ID to get units for"),
    current_user: dict = Depends(get_current_user)
):
    """List all units for a specific property"""
    try:
        user_id = current_user["sub"]
        
        # Verify property exists and belongs to user
        if not table_exists(NAMESPACE, PROPERTIES_TABLE):
            return UnitListResponse(items=[], total=0)
        
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        property_row = properties_df[
            (properties_df["id"] == property_id) & 
            (properties_df["user_id"] == user_id)
        ]
        
        if len(property_row) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Get units for this property
        if not table_exists(NAMESPACE, TABLE_NAME):
            return UnitListResponse(items=[], total=0)
        
        units_df = read_table(NAMESPACE, TABLE_NAME)
        property_units = units_df[
            (units_df["property_id"] == property_id) & 
            (units_df["is_active"] == True)
        ]
        
        total = len(property_units)
        
        # Convert to response objects
        items = []
        for _, row in property_units.iterrows():
            unit_dict = {
                "id": str(row["id"]),
                "property_id": str(row["property_id"]),
                "unit_number": row.get("unit_number"),
                "bedrooms": int(row["bedrooms"]) if pd.notna(row.get("bedrooms")) else None,
                "bathrooms": Decimal(str(row["bathrooms"])) if pd.notna(row.get("bathrooms")) else None,
                "square_feet": int(row["square_feet"]) if pd.notna(row.get("square_feet")) else None,
                "current_monthly_rent": Decimal(str(row["current_monthly_rent"])) if pd.notna(row.get("current_monthly_rent")) else None,
                "notes": row.get("notes"),
                "is_active": bool(row["is_active"]) if pd.notna(row.get("is_active")) else True,
                "created_at": row["created_at"] if pd.notna(row.get("created_at")) else pd.Timestamp.now(),
                "updated_at": row["updated_at"] if pd.notna(row.get("updated_at")) else pd.Timestamp.now(),
            }
            items.append(UnitResponse(**unit_dict))
        
        return UnitListResponse(items=items, total=total)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing units: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{unit_id}", response_model=UnitResponse)
async def get_unit_endpoint(
    unit_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific unit"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Unit not found")
        
        units_df = read_table(NAMESPACE, TABLE_NAME)
        unit_row = units_df[units_df["id"] == unit_id]
        
        if len(unit_row) == 0:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Verify property belongs to user
        property_id = str(unit_row.iloc[0]["property_id"])
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        property_row = properties_df[
            (properties_df["id"] == property_id) & 
            (properties_df["user_id"] == user_id)
        ]
        
        if len(property_row) == 0:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        row = unit_row.iloc[0]
        unit_dict = {
            "id": str(row["id"]),
            "property_id": str(row["property_id"]),
            "unit_number": row.get("unit_number"),
            "bedrooms": int(row["bedrooms"]) if pd.notna(row.get("bedrooms")) else None,
            "bathrooms": Decimal(str(row["bathrooms"])) if pd.notna(row.get("bathrooms")) else None,
            "square_feet": int(row["square_feet"]) if pd.notna(row.get("square_feet")) else None,
            "current_monthly_rent": Decimal(str(row["current_monthly_rent"])) if pd.notna(row.get("current_monthly_rent")) else None,
            "notes": row.get("notes"),
            "is_active": bool(row["is_active"]) if pd.notna(row.get("is_active")) else True,
            "created_at": row["created_at"] if pd.notna(row.get("created_at")) else pd.Timestamp.now(),
            "updated_at": row["updated_at"] if pd.notna(row.get("updated_at")) else pd.Timestamp.now(),
        }
        
        return UnitResponse(**unit_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting unit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{unit_id}", response_model=UnitResponse)
async def update_unit_endpoint(
    unit_id: str,
    unit_data: UnitUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a unit"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Read and update
        df = read_table(NAMESPACE, TABLE_NAME)
        mask = df["id"] == unit_id
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Verify property belongs to user
        property_id = str(df[mask].iloc[0]["property_id"])
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        property_row = properties_df[
            (properties_df["id"] == property_id) & 
            (properties_df["user_id"] == user_id)
        ]
        
        if len(property_row) == 0:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Update fields
        update_dict = unit_data.model_dump(exclude_none=True)
        for key, value in update_dict.items():
            if key in df.columns:
                if key in ["bathrooms", "current_monthly_rent"]:
                    df.loc[mask, key] = Decimal(str(value)) if value is not None else None
                else:
                    df.loc[mask, key] = value
        
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Convert timestamps to microseconds
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype('datetime64[us]')
        
        # Load table and get its schema
        table = load_table(NAMESPACE, TABLE_NAME)
        table_schema = table.schema().as_arrow()
        
        # Reorder DataFrame columns to match table schema
        schema_column_order = [field.name for field in table_schema]
        df = df[[col for col in schema_column_order if col in df.columns]]
        
        # Convert to PyArrow and cast to table schema
        import pyarrow as pa
        arrow_table = pa.Table.from_pandas(df)
        arrow_table = arrow_table.cast(table_schema)
        
        # Overwrite the table
        table.overwrite(arrow_table)
        
        # Get updated unit
        updated_row = df[mask].iloc[0]
        unit_dict = {
            "id": str(updated_row["id"]),
            "property_id": str(updated_row["property_id"]),
            "unit_number": updated_row.get("unit_number"),
            "bedrooms": int(updated_row["bedrooms"]) if pd.notna(updated_row.get("bedrooms")) else None,
            "bathrooms": Decimal(str(updated_row["bathrooms"])) if pd.notna(updated_row.get("bathrooms")) else None,
            "square_feet": int(updated_row["square_feet"]) if pd.notna(updated_row.get("square_feet")) else None,
            "current_monthly_rent": Decimal(str(updated_row["current_monthly_rent"])) if pd.notna(updated_row.get("current_monthly_rent")) else None,
            "notes": updated_row.get("notes"),
            "is_active": bool(updated_row["is_active"]) if pd.notna(updated_row.get("is_active")) else True,
            "created_at": updated_row["created_at"] if pd.notna(updated_row.get("created_at")) else pd.Timestamp.now(),
            "updated_at": updated_row["updated_at"] if pd.notna(updated_row.get("updated_at")) else pd.Timestamp.now(),
        }
        
        return UnitResponse(**unit_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating unit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{unit_id}", status_code=204)
async def delete_unit_endpoint(
    unit_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a unit (soft delete)"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Read table
        df = read_table(NAMESPACE, TABLE_NAME)
        mask = df["id"] == unit_id
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Verify property belongs to user
        property_id = str(df[mask].iloc[0]["property_id"])
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        property_row = properties_df[
            (properties_df["id"] == property_id) & 
            (properties_df["user_id"] == user_id)
        ]
        
        if len(property_row) == 0:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Soft delete
        df.loc[mask, "is_active"] = False
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Convert timestamps to microseconds
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype('datetime64[us]')
        
        # Load table and get its schema
        table = load_table(NAMESPACE, TABLE_NAME)
        table_schema = table.schema().as_arrow()
        
        # Reorder DataFrame columns to match table schema
        schema_column_order = [field.name for field in table_schema]
        df = df[[col for col in schema_column_order if col in df.columns]]
        
        # Convert to PyArrow and cast to table schema
        import pyarrow as pa
        arrow_table = pa.Table.from_pandas(df)
        arrow_table = arrow_table.cast(table_schema)
        
        # Overwrite the table
        table.overwrite(arrow_table)
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting unit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

