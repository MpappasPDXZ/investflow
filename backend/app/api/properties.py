"""API routes for property management"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID
import uuid
import pandas as pd
from decimal import Decimal
from datetime import date

from app.core.dependencies import get_current_user
from app.schemas.property import (
    PropertyCreate, PropertyUpdate, PropertyResponse, PropertyListResponse
)
from app.core.iceberg import read_table, append_data, table_exists, load_table
from app.core.logging import get_logger
from app.api.vacancy_utils import create_or_update_vacancy_expenses
from app.api.tax_savings_utils import create_or_update_tax_savings

NAMESPACE = ("investflow",)
TABLE_NAME = "properties"

router = APIRouter(prefix="/properties", tags=["properties"])
logger = get_logger(__name__)


@router.post("", response_model=PropertyResponse, status_code=201)
async def create_property_endpoint(
    property_data: PropertyCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new property in Iceberg"""
    try:
        user_id = current_user["sub"]  # Already a string
        property_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        # Create property record
        property_dict = {
            "id": property_id,
            "user_id": user_id,
            "display_name": property_data.display_name,
            "purchase_price": Decimal(str(property_data.purchase_price)),
            "purchase_date": property_data.purchase_date if property_data.purchase_date else date(2025, 10, 23),
            "down_payment": Decimal(str(property_data.down_payment)) if property_data.down_payment else None,
            "current_market_value": Decimal(str(property_data.current_market_value)) if property_data.current_market_value else None,
            "property_status": property_data.property_status if property_data.property_status else "evaluating",
            "vacancy_rate": Decimal(str(property_data.vacancy_rate)) if property_data.vacancy_rate else Decimal("0.07"),
            "monthly_rent_to_income_ratio": Decimal(str(property_data.monthly_rent_to_income_ratio)) if property_data.monthly_rent_to_income_ratio else None,
            "address_line1": property_data.address_line1,
            "address_line2": property_data.address_line2,
            "city": property_data.city,
            "state": property_data.state,
            "zip_code": property_data.zip_code,
            "property_type": property_data.property_type,
            "has_units": property_data.has_units if property_data.has_units is not None else False,
            "unit_count": property_data.unit_count,
            "bedrooms": property_data.bedrooms,
            "bathrooms": Decimal(str(property_data.bathrooms)) if property_data.bathrooms else None,
            "square_feet": property_data.square_feet,
            "year_built": property_data.year_built,
            "current_monthly_rent": Decimal(str(property_data.current_monthly_rent)) if property_data.current_monthly_rent else None,
            "notes": property_data.notes,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
        }
        
        # Append to Iceberg table
        df = pd.DataFrame([property_dict])
        append_data(NAMESPACE, TABLE_NAME, df)
        
        # Create vacancy expenses if square footage is available
        if property_data.square_feet and property_data.square_feet > 0:
            vacancy_rate = property_dict["vacancy_rate"]
            await create_or_update_vacancy_expenses(
                property_id=property_id,
                square_feet=property_data.square_feet,
                vacancy_rate=vacancy_rate
            )
        
        # Create tax savings (depreciation) revenue
        await create_or_update_tax_savings(
            property_id=property_id,
            purchase_price=property_data.purchase_price,
            purchase_date=property_dict["purchase_date"]
        )
        
        # Convert to response (UUID conversion)
        response_dict = property_dict.copy()
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
    """List all properties for the current user from Iceberg"""
    try:
        user_id = current_user["sub"]  # Already a string
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            return PropertyListResponse(items=[], total=0, page=1, limit=limit)
        
        # Read all properties for user
        df = read_table(NAMESPACE, TABLE_NAME)
        user_properties = df[(df["user_id"] == user_id) & (df["is_active"] == True)]
        
        total = len(user_properties)
        
        # Apply pagination
        paginated = user_properties.iloc[skip:skip + limit]
        
        # Convert to PropertyResponse objects
        items = []
        for _, row in paginated.iterrows():
            prop_dict = {
                "id": UUID(str(row["id"])),
                "user_id": UUID(str(row["user_id"])),
                "display_name": row.get("display_name"),
                "purchase_price": Decimal(str(row["purchase_price"])),
                "down_payment": Decimal(str(row["down_payment"])) if pd.notna(row.get("down_payment")) else None,
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
            items.append(PropertyResponse(**prop_dict))
        
        return PropertyListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error listing properties: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property_endpoint(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a property by ID from Iceberg"""
    try:
        user_id = current_user["sub"]  # Already a string
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Read table and find property
        df = read_table(NAMESPACE, TABLE_NAME)
        property_rows = df[(df["id"] == property_id) & (df["user_id"] == user_id)]
        
        if len(property_rows) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        row = property_rows.iloc[0]
        
        # Convert to response
        prop_dict = {
            "id": UUID(str(row["id"])),
            "user_id": UUID(str(row["user_id"])),
            "display_name": row.get("display_name"),
            "purchase_price": Decimal(str(row["purchase_price"])),
            "down_payment": Decimal(str(row["down_payment"])) if pd.notna(row.get("down_payment")) else None,
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
    """Update a property in Iceberg"""
    try:
        user_id = current_user["sub"]  # Already a string
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Read table, update, and write back (Iceberg update pattern)
        df = read_table(NAMESPACE, TABLE_NAME)
        mask = (df["id"] == property_id) & (df["user_id"] == user_id)
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Update fields
        update_dict = property_data.model_dump(exclude_none=True)
        logger.info(f"Update dict received: {update_dict}")
        
        for key, value in update_dict.items():
            logger.info(f"Processing key: {key}, in columns: {key in df.columns}")
            if key in df.columns:
                logger.info(f"Updating {key} with value {value} (type: {type(value)})")
                # Convert Decimal fields
                if key in ["purchase_price", "down_payment", "current_market_value", "vacancy_rate", "monthly_rent_to_income_ratio", "bathrooms", "current_monthly_rent"]:
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
        
        # Check if purchase price or purchase date changed - update tax savings
        if "purchase_price" in update_dict or "purchase_date" in update_dict:
            updated_row = df[mask].iloc[0]
            purchase_price = Decimal(str(updated_row["purchase_price"]))
            purchase_date = updated_row.get("purchase_date")
            if pd.notna(purchase_date):
                purchase_date = purchase_date.date() if hasattr(purchase_date, 'date') else purchase_date
            else:
                purchase_date = date(2025, 10, 23)
            
            logger.info(f"Updating tax savings: purchase_price=${purchase_price}, purchase_date={purchase_date}")
            await create_or_update_tax_savings(
                property_id=property_id,
                purchase_price=purchase_price,
                purchase_date=purchase_date
            )
        
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
        
        # Get updated property
        updated_row = df[mask].iloc[0]
        logger.info(f"Updated row property_status: {updated_row.get('property_status')}")
        
        # Convert to response
        prop_dict = {
            "id": UUID(str(updated_row["id"])),
            "user_id": UUID(str(updated_row["user_id"])),
            "display_name": updated_row.get("display_name"),
            "purchase_price": Decimal(str(updated_row["purchase_price"])),
            "down_payment": Decimal(str(updated_row["down_payment"])) if pd.notna(updated_row.get("down_payment")) else None,
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
    """Delete a property (soft delete) in Iceberg"""
    try:
        user_id = current_user["sub"]  # Already a string
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Verify property exists and belongs to user before soft delete
        df = read_table(NAMESPACE, TABLE_NAME)
        mask = (df["id"] == property_id) & (df["user_id"] == user_id) & (df["is_active"] == True)
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Property not found")
        
        # SOFT DELETE: Update is_active to False (we keep the data)
        # For hard delete, we would use: table.delete(And(EqualTo("id", property_id), EqualTo("user_id", user_id)))
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
        logger.error(f"Error deleting property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
