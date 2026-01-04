"""Expense service for managing expenses in Iceberg"""
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pyiceberg.expressions import EqualTo, And, GreaterThanOrEqual, LessThanOrEqual
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.core.iceberg import get_catalog
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExpenseService:
    """Service for managing expenses in Iceberg"""
    
    def __init__(self):
        self.catalog = get_catalog()
        self.namespace = "investflow"
        self.table_name = "expenses"
        self._table_cache = None
        self._table_cache_time = None
        self._cache_ttl = 60  # Cache table reference for 60 seconds
        # Import here to avoid circular dependency
        self._financial_performance_service = None
    
    def _get_financial_performance_service(self):
        """Lazy load financial performance service to avoid circular imports"""
        if self._financial_performance_service is None:
            from app.services.financial_performance_service import financial_performance_service
            self._financial_performance_service = financial_performance_service
        return self._financial_performance_service
    
    def _get_table(self, use_cache=True):
        """Get the expenses table with caching"""
        import time
        now = time.time()
        
        # Return cached table if still valid
        if use_cache and self._table_cache is not None and self._table_cache_time is not None:
            if now - self._table_cache_time < self._cache_ttl:
                return self._table_cache
        
        # Load table and cache it
        self._table_cache = self.catalog.load_table(f"{self.namespace}.{self.table_name}")
        self._table_cache_time = now
        return self._table_cache
    
    def create_expense(
        self,
        user_id: uuid.UUID,
        expense_data: ExpenseCreate
    ) -> Dict[str, Any]:
        """
        Create a new expense
        
        Args:
            user_id: User creating the expense
            expense_data: Expense data
        
        Returns:
            Created expense dictionary
        """
        try:
            # Get fresh table reference for writes to avoid lock issues
            table = self.catalog.load_table(f"{self.namespace}.{self.table_name}")
            
            expense_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            # Set has_receipt based on document_storage_id
            has_receipt = expense_data.document_storage_id is not None
            
            # Build record in EXACT Iceberg table field order:
            # id, property_id, unit_id, description, vendor, expense_type, expense_category, 
            # document_storage_id, notes, amount, date, has_receipt, created_at, updated_at
            record = {
                "id": expense_id,
                "property_id": str(expense_data.property_id),
                "unit_id": str(expense_data.unit_id) if expense_data.unit_id else None,
                "description": expense_data.description,
                "vendor": expense_data.vendor,
                "expense_type": expense_data.expense_type.value,
                "expense_category": expense_data.expense_category.value if expense_data.expense_category else None,
                "document_storage_id": str(expense_data.document_storage_id) if expense_data.document_storage_id else None,
                "notes": expense_data.notes,
                "amount": Decimal(str(expense_data.amount)),  # Convert to Decimal
                "date": expense_data.date,
                "has_receipt": has_receipt,
                "created_at": now,
                "updated_at": now
            }
            
            # Write to Iceberg
            import pyarrow as pa
            schema = table.schema().as_arrow()
            arrow_table = pa.Table.from_pylist([record], schema=schema)
            table.append(arrow_table)
            
            logger.info(f"Created expense: {expense_id}")
            
            # Invalidate cache after write to ensure fresh table for next operation
            self._table_cache = None
            self._table_cache_time = None
            
            # Invalidate financial performance cache for this property (async, non-blocking)
            try:
                import asyncio
                fp_service = self._get_financial_performance_service()
                # Fire and forget - don't block expense creation
                asyncio.create_task(
                    asyncio.to_thread(
                        fp_service.invalidate_cache,
                        expense_data.property_id,
                        user_id,  # Pass user_id for recalculation
                        expense_data.unit_id
                    )
                )
            except Exception as cache_err:
                logger.warning(f"Failed to queue financial performance cache invalidation: {cache_err}")
            
            return record
            
        except Exception as e:
            logger.error(f"Error creating expense: {e}", exc_info=True)
            raise
    
    def get_expense(
        self,
        expense_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get an expense by ID
        
        Args:
            expense_id: Expense ID
        
        Returns:
            Expense dictionary or None if not found
        """
        try:
            import time
            start = time.time()
            
            # Force fresh table load to avoid stale cache issues
            table = self._get_table(use_cache=False)
            logger.info(f"[PERF] get_expense: Table loaded in {time.time() - start:.3f}s")
            
            scan_start = time.time()
            # Query for the expense by ID only
            expense_id_str = str(expense_id)
            logger.info(f"[DEBUG] get_expense: Searching for expense_id: {expense_id_str} (type: {type(expense_id_str)})")
            
            # Try without limit first to see if limit is causing issues
            scan = table.scan(
                row_filter=EqualTo("id", expense_id_str)
            )
            
            logger.info(f"[PERF] get_expense: Scan setup in {time.time() - scan_start:.3f}s")
            
            arrow_start = time.time()
            # Get first result - scan.to_arrow() returns a Table
            arrow_table = scan.to_arrow()
            logger.info(f"[PERF] get_expense: Arrow conversion in {time.time() - arrow_start:.3f}s")
            logger.info(f"[DEBUG] get_expense: Found {len(arrow_table)} rows for expense_id: {expense_id_str}")
            
            # If we got results, take the first one
            if len(arrow_table) > 0:
                arrow_table = arrow_table.slice(0, 1)  # Take only first row
            
            if len(arrow_table) > 0:
                result = arrow_table.to_pylist()[0]
                # Clean up data: convert 'None' strings to None
                if result.get('unit_id') == 'None' or result.get('unit_id') == '':
                    result['unit_id'] = None
                # Ensure unit_id is UUID or None
                if result.get('unit_id') and not isinstance(result['unit_id'], uuid.UUID):
                    try:
                        result['unit_id'] = uuid.UUID(result['unit_id'])
                    except (ValueError, TypeError):
                        result['unit_id'] = None
                
                # Convert 'None' strings to None for document_storage_id
                if result.get('document_storage_id') == 'None' or result.get('document_storage_id') == '':
                    result['document_storage_id'] = None
                # Ensure document_storage_id is UUID or None
                if result.get('document_storage_id') and not isinstance(result['document_storage_id'], uuid.UUID):
                    try:
                        result['document_storage_id'] = uuid.UUID(result['document_storage_id'])
                    except (ValueError, TypeError):
                        result['document_storage_id'] = None
                
                # Ensure has_receipt is a proper Python bool (not numpy.bool_)
                if 'has_receipt' in result:
                    if result['has_receipt'] is None:
                        result['has_receipt'] = result.get('document_storage_id') is not None
                    else:
                        result['has_receipt'] = bool(result['has_receipt'])
                
                logger.info(f"[PERF] get_expense: Total time {time.time() - start:.3f}s")
                logger.info(f"[DEBUG] Retrieved expense date: {result.get('date')} (type: {type(result.get('date'))})")
                return result
            
            logger.info(f"[PERF] get_expense: Not found, total time {time.time() - start:.3f}s")
            return None
            
        except Exception as e:
            logger.error(f"Error getting expense: {e}", exc_info=True)
            return None
    
    def list_expenses(
        self,
        property_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        expense_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List expenses filtered by property_id and optional filters
        
        Args:
            property_id: Property ID (required for filtering)
            unit_id: Optional unit filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            expense_type: Optional expense type filter
            skip: Number of records to skip
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (list of expenses, total count)
        """
        try:
            table = self._get_table()
            
            # Build filter - property_id is required
            filters = []
            
            if not property_id:
                # If no property_id provided, return empty (expenses are stored by property_id)
                return [], 0
            
            filters.append(EqualTo("property_id", str(property_id)))
            
            if unit_id:
                filters.append(EqualTo("unit_id", str(unit_id)))
            
            if start_date:
                filters.append(GreaterThanOrEqual("date", start_date))
            
            if end_date:
                filters.append(LessThanOrEqual("date", end_date))
            
            if expense_type:
                filters.append(EqualTo("expense_type", expense_type))
            
            # Combine filters
            if len(filters) > 0:
                row_filter = filters[0]
                for f in filters[1:]:
                    row_filter = And(row_filter, f)
                
                # Query
                scan = table.scan(row_filter=row_filter)
            else:
                # Should not happen since property_id is required
                return [], 0
            
            # Collect all results - scan.to_arrow() returns a Table
            arrow_table = scan.to_arrow()
            all_expenses = arrow_table.to_pylist()
            
            # Clean up data: convert 'None' strings to None, and ensure proper types
            for expense in all_expenses:
                # Convert 'None' strings to None for unit_id
                if expense.get('unit_id') == 'None' or expense.get('unit_id') == '':
                    expense['unit_id'] = None
                # Ensure unit_id is UUID or None
                if expense.get('unit_id') and not isinstance(expense['unit_id'], uuid.UUID):
                    try:
                        expense['unit_id'] = uuid.UUID(expense['unit_id'])
                    except (ValueError, TypeError):
                        expense['unit_id'] = None
                
                # Convert 'None' strings to None for document_storage_id
                if expense.get('document_storage_id') == 'None' or expense.get('document_storage_id') == '':
                    expense['document_storage_id'] = None
                # Ensure document_storage_id is UUID or None
                if expense.get('document_storage_id') and not isinstance(expense['document_storage_id'], uuid.UUID):
                    try:
                        expense['document_storage_id'] = uuid.UUID(expense['document_storage_id'])
                    except (ValueError, TypeError):
                        expense['document_storage_id'] = None
                
                # Ensure has_receipt is a proper Python bool (not numpy.bool_)
                if 'has_receipt' in expense:
                    if expense['has_receipt'] is None:
                        expense['has_receipt'] = expense.get('document_storage_id') is not None
                    else:
                        expense['has_receipt'] = bool(expense['has_receipt'])
            
            # Deduplicate by expense ID - keep the most recent version (by updated_at)
            expense_dict = {}
            for expense in all_expenses:
                expense_id = expense.get('id')
                if expense_id:
                    if expense_id not in expense_dict:
                        expense_dict[expense_id] = expense
                    else:
                        # Keep the one with the latest updated_at
                        existing_updated = expense_dict[expense_id].get('updated_at')
                        current_updated = expense.get('updated_at')
                        if current_updated and existing_updated:
                            if current_updated > existing_updated:
                                expense_dict[expense_id] = expense
                        elif current_updated:
                            expense_dict[expense_id] = expense
            
            all_expenses = list(expense_dict.values())
            
            # Sort by date descending
            all_expenses.sort(key=lambda x: x["date"], reverse=True)
            
            total = len(all_expenses)
            paginated_expenses = all_expenses[skip:skip + limit]
            
            return paginated_expenses, total
            
        except Exception as e:
            logger.error(f"Error listing expenses: {e}", exc_info=True)
            return [], 0
    
    def get_expense_summary(
        self,
        property_id: uuid.UUID,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get expense summary with yearly subtotals for a property
        
        Args:
            property_id: Property ID (required)
            year: Optional year filter
        
        Returns:
            Summary dictionary with yearly subtotals
        """
        try:
            table = self._get_table()
            
            # Build filter - property_id is required
            filters = [EqualTo("property_id", str(property_id))]
            
            # Combine filters
            row_filter = filters[0]
            for f in filters[1:]:
                row_filter = And(row_filter, f)
            
            # Query
            scan = table.scan(row_filter=row_filter)
            
            # Collect all results - scan.to_arrow() returns a Table
            arrow_table = scan.to_arrow()
            all_expenses = arrow_table.to_pylist()
            
            # Calculate summaries
            yearly_totals = {}
            type_totals = {}
            
            for expense in all_expenses:
                expense_date = expense["date"]
                expense_year = expense_date.year if hasattr(expense_date, 'year') else None
                
                if expense_year:
                    if year and expense_year != year:
                        continue
                    
                    # Yearly totals
                    if expense_year not in yearly_totals:
                        yearly_totals[expense_year] = {
                            "year": expense_year,
                            "total": 0,
                            "count": 0,
                            "by_type": {}
                        }
                    
                    yearly_totals[expense_year]["total"] += float(expense["amount"])
                    yearly_totals[expense_year]["count"] += 1
                    
                    # By type within year
                    exp_type = expense["expense_type"]
                    if exp_type not in yearly_totals[expense_year]["by_type"]:
                        yearly_totals[expense_year]["by_type"][exp_type] = 0
                    yearly_totals[expense_year]["by_type"][exp_type] += float(expense["amount"])
                    
                    # Overall type totals
                    if exp_type not in type_totals:
                        type_totals[exp_type] = 0
                    type_totals[exp_type] += float(expense["amount"])
            
            # Sort yearly totals
            yearly_list = sorted(yearly_totals.values(), key=lambda x: x["year"], reverse=True)
            
            return {
                "yearly_totals": yearly_list,
                "type_totals": type_totals,
                "grand_total": sum(y["total"] for y in yearly_list),
                "total_count": sum(y["count"] for y in yearly_list)
            }
            
        except Exception as e:
            logger.error(f"Error getting expense summary: {e}", exc_info=True)
            return {
                "yearly_totals": [],
                "type_totals": {},
                "grand_total": 0,
                "total_count": 0
            }
    
    def update_expense(
        self,
        expense_id: uuid.UUID,
        expense_data: ExpenseUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        Update an expense
        
        Args:
            expense_id: Expense ID
            expense_data: Updated expense data
        
        Returns:
            Updated expense dictionary or None if not found
        """
        try:
            logger.info(f"[UPDATE] Getting existing expense {expense_id}")
            # Get existing expense
            existing = self.get_expense(expense_id)
            
            if not existing:
                logger.warning(f"[UPDATE] Expense {expense_id} not found in database")
                return None
            
            logger.info(f"[UPDATE] Found existing expense {expense_id}, property_id: {existing.get('property_id')}")
            
            # Update fields
            update_dict = expense_data.model_dump(exclude_unset=True)
            logger.info(f"[DEBUG] Update dict before processing: {update_dict}")
            
            # Track if document_storage_id is being updated
            document_storage_id_updated = "document_storage_id" in update_dict
            
            for key, value in update_dict.items():
                if value is not None:
                    if key in ["property_id", "unit_id", "document_storage_id"] and value:
                        existing[key] = str(value)
                    elif key in ["expense_type", "expense_category"] and value:
                        existing[key] = value.value
                    elif key == "amount" and value:
                        existing[key] = Decimal(str(value))
                    elif key == "date" and value:
                        logger.info(f"[DEBUG] Updating date: {value} (type: {type(value)})")
                        existing[key] = value
                    elif key == "has_receipt":
                        # Explicit has_receipt update
                        existing[key] = value
                    else:
                        existing[key] = value
            
            # Update has_receipt if document_storage_id was changed but has_receipt wasn't explicitly set
            if document_storage_id_updated and "has_receipt" not in update_dict:
                existing["has_receipt"] = existing.get("document_storage_id") is not None and existing.get("document_storage_id") != "None" and existing.get("document_storage_id") != ""
            
            # Ensure has_receipt exists (for backward compatibility with old records)
            if "has_receipt" not in existing:
                existing["has_receipt"] = existing.get("document_storage_id") is not None and existing.get("document_storage_id") != "None" and existing.get("document_storage_id") != ""
            
            logger.info(f"[DEBUG] Date after update: {existing.get('date')} (type: {type(existing.get('date'))})")
            existing["updated_at"] = datetime.utcnow()
            
            # Ensure amount is Decimal (it may come back as float from Iceberg)
            if "amount" in existing and not isinstance(existing["amount"], Decimal):
                existing["amount"] = Decimal(str(existing["amount"]))
            
            # Use efficient upsert instead of delete+append
            import pandas as pd
            from app.core.iceberg import upsert_data_with_schema_cast
            
            # Ensure all UUID fields are strings (not UUID objects) before creating DataFrame
            # get_expense() converts UUID strings to UUID objects, but DataFrame needs strings
            existing_for_df = existing.copy()
            uuid_fields = ['id', 'property_id', 'unit_id', 'document_storage_id']
            for field in uuid_fields:
                if field in existing_for_df:
                    value = existing_for_df[field]
                    if value is None:
                        existing_for_df[field] = None
                    elif isinstance(value, uuid.UUID):
                        existing_for_df[field] = str(value)
                    elif value == 'None' or value == '':
                        existing_for_df[field] = None
                    else:
                        # Already a string, keep it
                        existing_for_df[field] = str(value)
            
            # Also ensure date is a date object (not datetime)
            if 'date' in existing_for_df and existing_for_df['date']:
                if isinstance(existing_for_df['date'], datetime):
                    existing_for_df['date'] = existing_for_df['date'].date()
            
            # Rebuild dict in EXACT Iceberg table field order:
            # id, property_id, unit_id, description, vendor, expense_type, expense_category, 
            # document_storage_id, notes, amount, date, has_receipt, created_at, updated_at
            ordered_dict = {
                "id": existing_for_df.get("id"),
                "property_id": existing_for_df.get("property_id"),
                "unit_id": existing_for_df.get("unit_id"),
                "description": existing_for_df.get("description"),
                "vendor": existing_for_df.get("vendor"),
                "expense_type": existing_for_df.get("expense_type"),
                "expense_category": existing_for_df.get("expense_category"),
                "document_storage_id": existing_for_df.get("document_storage_id"),
                "notes": existing_for_df.get("notes"),
                "amount": existing_for_df.get("amount"),
                "date": existing_for_df.get("date"),
                "has_receipt": existing_for_df.get("has_receipt"),
                "created_at": existing_for_df.get("created_at"),
                "updated_at": existing_for_df.get("updated_at")
            }
            
            # Convert ordered dict to DataFrame for upsert
            df = pd.DataFrame([ordered_dict])
            
            # Handle potential duplicate rows by deleting all existing rows with this ID first
            # This ensures we don't hit "duplicate rows" errors during upsert
            try:
                table = self._get_table()
                # Delete all existing rows with this ID (handles duplicates)
                # Note: table.delete() takes the expression directly, not as a keyword argument
                table.delete(EqualTo("id", str(expense_id)))
                logger.info(f"[UPDATE] Deleted existing row(s) for expense {expense_id}, appending updated row")
                
                # Append the updated row (since we deleted the old one)
                from app.core.iceberg import append_data
                append_data(
                    namespace=(self.namespace,),
                    table_name=self.table_name,
                    data=df
                )
            except Exception as delete_error:
                logger.warning(f"[UPDATE] Error during delete-append: {delete_error}, trying upsert instead")
                # Fallback to upsert if delete-append fails
                upsert_data_with_schema_cast(
                    namespace=(self.namespace,),
                    table_name=self.table_name,
                    data=df,
                    join_cols=["id"]
                )
            
            logger.info(f"Updated expense: {expense_id}")
            
            # Invalidate cache after write
            self._table_cache = None
            self._table_cache_time = None
            
            # Invalidate financial performance cache for this property (non-blocking)
            try:
                fp_service = self._get_financial_performance_service()
                fp_service.invalidate_cache(
                    property_id=uuid.UUID(existing['property_id']),
                    user_id=None,  # user_id not needed for cache invalidation
                    unit_id=uuid.UUID(existing['unit_id']) if existing.get('unit_id') else None
                )
            except Exception as cache_err:
                logger.warning(f"Failed to invalidate financial performance cache: {cache_err}")
            
            return existing
            
        except Exception as e:
            logger.error(f"Error updating expense: {e}", exc_info=True)
            return None
    
    def delete_expense(
        self,
        expense_id: uuid.UUID
    ) -> bool:
        """
        Delete an expense
        
        Args:
            expense_id: Expense ID
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify expense exists
            existing = self.get_expense(expense_id)
            
            if not existing:
                return False
            
            # Get fresh table reference for writes to avoid lock issues
            table = self.catalog.load_table(f"{self.namespace}.{self.table_name}")
            
            table.delete(EqualTo("id", str(expense_id)))
            
            logger.info(f"Deleted expense: {expense_id}")
            
            # Invalidate cache after write
            self._table_cache = None
            self._table_cache_time = None
            
            # Invalidate financial performance cache for this property
            try:
                fp_service = self._get_financial_performance_service()
                fp_service.invalidate_cache(
                    property_id=uuid.UUID(existing['property_id']),
                    user_id=None,  # user_id not needed for cache invalidation
                    unit_id=uuid.UUID(existing['unit_id']) if existing.get('unit_id') else None
                )
            except Exception as cache_err:
                logger.warning(f"Failed to invalidate financial performance cache: {cache_err}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting expense: {e}", exc_info=True)
            return False


# Global instance
expense_service = ExpenseService()


# Convenience functions for use in API routes
def create_expense(user_id: uuid.UUID, expense_data: ExpenseCreate) -> Dict[str, Any]:
    """Create an expense"""
    return expense_service.create_expense(user_id, expense_data)


def get_expense(expense_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Get an expense by ID"""
    return expense_service.get_expense(expense_id)


def list_expenses(
    property_id: Optional[uuid.UUID] = None,
    unit_id: Optional[uuid.UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    expense_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Dict[str, Any]], int]:
    """List expenses with filters (property_id required)"""
    return expense_service.list_expenses(
        property_id=property_id,
        unit_id=unit_id,
        start_date=start_date,
        end_date=end_date,
        expense_type=expense_type,
        skip=skip,
        limit=limit
    )


def get_expense_summary(
    property_id: uuid.UUID,
    year: Optional[int] = None
) -> Dict[str, Any]:
    """Get expense summary with yearly subtotals for a property"""
    return expense_service.get_expense_summary(
        property_id=property_id,
        year=year
    )


def update_expense(
    expense_id: uuid.UUID,
    expense_data: ExpenseUpdate
) -> Optional[Dict[str, Any]]:
    """Update an expense"""
    return expense_service.update_expense(expense_id, expense_data)


def delete_expense(expense_id: uuid.UUID) -> bool:
    """Delete an expense"""
    return expense_service.delete_expense(expense_id)
