"""
API endpoints for scheduled financials template management
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from app.core.dependencies import get_current_user
from app.services.scheduled_financials_template_service import scheduled_financials_template
from app.core.iceberg import read_table, table_exists, get_catalog
from app.core.logging import get_logger
from typing import Dict, Any, List
import uuid
import pandas as pd
import pyarrow as pa
from datetime import timezone
from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter()

NAMESPACE = ("investflow",)

# Import field order constants
from app.api.scheduled import SCHEDULED_EXPENSES_FIELD_ORDER, SCHEDULED_REVENUE_FIELD_ORDER


def _append_template_expenses(expenses_list: List[Dict[str, Any]]):
    """Append multiple scheduled expenses with strict field ordering (dedicated function for template)"""
    try:
        from app.api.scheduled import _load_scheduled_expenses_table
        table = _load_scheduled_expenses_table()
        table_schema = table.schema().as_arrow()
        actual_field_order = [f.name for f in table_schema]

        # Build DataFrame with fields in exact order matching ACTUAL table schema
        ordered_dicts = []
        for expense in expenses_list:
            ordered_dict = {}
            for field_name in actual_field_order:
                if field_name in expense:
                    ordered_dict[field_name] = expense[field_name]
                else:
                    ordered_dict[field_name] = None
            ordered_dicts.append(ordered_dict)

        df = pd.DataFrame(ordered_dicts)

        # Ensure DataFrame columns are in exact order matching table schema
        df = df[actual_field_order]

        # Convert timestamp columns to microseconds (handle timezone-aware timestamps)
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                # Handle timezone-aware timestamps
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    # If already datetime, check if timezone-aware
                    if df[col].dt.tz is not None:
                        # Convert to timezone-naive
                        df[col] = df[col].dt.tz_localize(None)
                    df[col] = df[col].dt.floor('us')
                else:
                    # Convert from string or other types
                    df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
                    df[col] = df[col].dt.floor('us')

        # Convert decimal columns with proper scale rounding (like iceberg.py append_data)
        from decimal import Decimal as PythonDecimal
        from pyiceberg.types import DecimalType

        # Get decimal scale from schema for each column
        current_schema = table.schema()
        decimal_scales = {}
        for field in current_schema.fields:
            if isinstance(field.field_type, DecimalType) and field.name in df.columns:
                decimal_scales[field.name] = field.field_type.scale

        decimal_cols = ['purchase_price', 'depreciation_rate', 'annual_cost', 'principal', 'interest_rate']
        for col in decimal_cols:
            if col in df.columns:
                scale = decimal_scales.get(col, 2)  # Default to 2 decimal places if not found
                def to_decimal(x, s=scale):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        # Round to schema scale to prevent precision loss (like iceberg.py)
                        return PythonDecimal(str(round(float(x), s)))
                    except (ValueError, TypeError):
                        return None
                df[col] = df[col].apply(to_decimal)

        # Convert count to float64 (double)
        if 'count' in df.columns:
            df['count'] = pd.to_numeric(df['count'], errors='coerce')

        # Convert to PyArrow and cast to schema (same pattern as _append_scheduled_expense)
        arrow_table = pa.Table.from_pandas(df)
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)

        table.append(arrow_table)
    except Exception as e:
        logger.error(f"Failed to append template expenses: {e}", exc_info=True)
        raise


def _append_template_revenue(revenue_list: List[Dict[str, Any]]):
    """Append multiple scheduled revenue with strict field ordering (dedicated function for template)"""
    try:
        from app.api.scheduled import _load_scheduled_revenue_table
        table = _load_scheduled_revenue_table()
        table_schema = table.schema().as_arrow()
        actual_field_order = [f.name for f in table_schema]

        # Build DataFrame with fields in exact order matching ACTUAL table schema
        ordered_dicts = []
        for revenue in revenue_list:
            ordered_dict = {}
            for field_name in actual_field_order:
                if field_name in revenue:
                    ordered_dict[field_name] = revenue[field_name]
                else:
                    ordered_dict[field_name] = None
            ordered_dicts.append(ordered_dict)

        df = pd.DataFrame(ordered_dicts)

        # Ensure DataFrame columns are in exact order matching table schema
        df = df[actual_field_order]

        # Convert timestamp columns to microseconds (same pattern as _append_scheduled_revenue)
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                # Convert to datetime if not already, handling both timezone-aware and naive
                df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
                # Ensure microseconds precision
                df[col] = df[col].dt.floor('us')

        # Convert double columns (same pattern as _append_scheduled_revenue)
        double_cols = ['annual_amount', 'appreciation_rate', 'property_value', 'value_added_amount']
        for col in double_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convert to PyArrow and cast to schema (same pattern as _append_scheduled_revenue)
        arrow_table = pa.Table.from_pandas(df)
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)

        table.append(arrow_table)
    except Exception as e:
        logger.error(f"Failed to append template revenue: {e}", exc_info=True)
        raise


class ApplyTemplateRequest(BaseModel):
    expenses: List[Dict[str, Any]]
    revenue: List[Dict[str, Any]]


@router.get("/scheduled-financials/preview-template/{property_id}")
async def preview_template(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Preview the template for a property with scaling applied (without saving).
    Returns the scaled expenses and revenue items for user selection.
    """
    try:
        user_id = current_user["sub"]

        # Get target property data
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) &
            (properties_df['user_id'] == user_id)
        ]

        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")

        property_data = property_match.iloc[0].to_dict()

        # Get scaled template
        from uuid import UUID
        result = scheduled_financials_template.apply_template_to_property(
            UUID(property_id),
            property_data
        )

        # Filter out principal and interest items
        filtered_expenses = [
            exp for exp in result["expenses"]
            if exp.get("expense_type") != "pi"
        ]

        return {
            "expenses": filtered_expenses,
            "revenue": result["revenue"],
            "scaling_factors": result["scaling_factors"]
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error previewing template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-financials/apply-template/{property_id}")
async def apply_template(
    property_id: str,
    request: ApplyTemplateRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Apply selected template items to a property.
    Accepts a list of expenses and revenue items to apply.
    """
    try:
        user_id = current_user["sub"]

        # Get target property data (verify ownership)
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) &
            (properties_df['user_id'] == user_id)
        ]

        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")

        # Insert selected expenses
        expenses_created = 0
        if request.expenses:
            for expense in request.expenses:
                expense["id"] = str(uuid.uuid4())
                expense["is_active"] = True
                expense["created_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
                expense["updated_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')

            # Use dedicated append function that respects column order
            _append_template_expenses(request.expenses)
            expenses_created = len(request.expenses)

        # Insert selected revenue
        revenue_created = 0
        if request.revenue:
            for rev in request.revenue:
                rev["id"] = str(uuid.uuid4())
                rev["is_active"] = True
                rev["created_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
                rev["updated_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')

            # Use dedicated append function that respects column order
            _append_template_revenue(request.revenue)
            revenue_created = len(request.revenue)

        return {
            "message": "Template applied successfully",
            "property_id": property_id,
            "expenses_created": expenses_created,
            "revenue_created": revenue_created
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/scheduled-financials/save-template/{property_id}")
async def save_template(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Save a property's scheduled financials as the template.
    This should be called on the reference property (316 S 50th Ave).
    """
    try:
        user_id = current_user["sub"]

        # Get property data
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) &
            (properties_df['user_id'] == user_id)
        ]

        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")

        property_data = property_match.iloc[0].to_dict()

        # Save as template
        from uuid import UUID
        success = scheduled_financials_template.save_template_from_property(
            UUID(property_id),
            property_data
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save template")

        return {
            "message": "Template saved successfully",
            "property_id": property_id,
            "property_address": property_data.get("address_line1")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-financials/template-info")
async def get_template_info(
    current_user: dict = Depends(get_current_user)
):
    """Get information about the current template"""
    try:
        scheduled_financials_template.initialize()

        if not scheduled_financials_template._template_metadata:
            return {
                "template_available": False,
                "message": "No template configured. Use 'save-template' on a reference property first."
            }

        # Get property address for display
        template_property_id = scheduled_financials_template._template_metadata.get("template_property_id")
        property_address = "Unknown"
        if template_property_id:
            try:
                properties_df = read_table(NAMESPACE, "properties")
                property_match = properties_df[properties_df['id'] == template_property_id]
                if not property_match.empty:
                    prop = property_match.iloc[0]
                    address_line1 = prop.get("address_line1", "")
                    city = prop.get("city", "")
                    state = prop.get("state", "")
                    if address_line1:
                        property_address = f"{address_line1}"
                        if city:
                            property_address += f", {city}"
                        if state:
                            property_address += f", {state}"
            except Exception as e:
                logger.warning(f"Could not fetch template property address: {e}")

        return {
            "template_available": True,
            "template_property_id": template_property_id,
            "template_property_address": property_address,
            "purchase_price": float(scheduled_financials_template._template_metadata.get("purchase_price", 0)),
            "bedrooms": float(scheduled_financials_template._template_metadata.get("bedrooms", 0)),
            "bathrooms": float(scheduled_financials_template._template_metadata.get("bathrooms", 0)),
            "square_feet": float(scheduled_financials_template._template_metadata.get("square_feet", 0)),
            "expenses_count": len(scheduled_financials_template._expenses_template),
            "revenue_count": len(scheduled_financials_template._revenue_template)
        }

    except Exception as e:
        logger.error(f"Error getting template info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

