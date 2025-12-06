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
    
    def _get_table(self):
        """Get the expenses table with caching"""
        import time
        now = time.time()
        
        # Return cached table if still valid
        if self._table_cache is not None and self._table_cache_time is not None:
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
            
            record = {
                "id": expense_id,
                "property_id": str(expense_data.property_id),
                "unit_id": str(expense_data.unit_id) if expense_data.unit_id else None,
                "description": expense_data.description,
                "date": expense_data.date,
                "amount": Decimal(str(expense_data.amount)),  # Convert to Decimal
                "vendor": expense_data.vendor,
                "expense_type": expense_data.expense_type.value,
                "expense_category": expense_data.expense_category.value if expense_data.expense_category else None,
                "document_storage_id": str(expense_data.document_storage_id) if expense_data.document_storage_id else None,
                "is_planned": expense_data.is_planned,
                "notes": expense_data.notes,
                "created_by_user_id": str(user_id),
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
            
            return record
            
        except Exception as e:
            logger.error(f"Error creating expense: {e}", exc_info=True)
            raise
    
    def get_expense(
        self,
        expense_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get an expense by ID (with user access check)
        
        Args:
            expense_id: Expense ID
            user_id: User ID for access control
        
        Returns:
            Expense dictionary or None if not found
        """
        try:
            import time
            start = time.time()
            
            table = self._get_table()
            logger.info(f"[PERF] get_expense: Table loaded in {time.time() - start:.3f}s")
            
            scan_start = time.time()
            # Query for the expense
            scan = table.scan(
                row_filter=And(
                    EqualTo("id", str(expense_id)),
                    EqualTo("created_by_user_id", str(user_id))
                ),
                limit=1  # Only need one result
            )
            
            logger.info(f"[PERF] get_expense: Scan setup in {time.time() - scan_start:.3f}s")
            
            arrow_start = time.time()
            # Get first result - scan.to_arrow() returns a Table
            arrow_table = scan.to_arrow()
            logger.info(f"[PERF] get_expense: Arrow conversion in {time.time() - arrow_start:.3f}s")
            
            if len(arrow_table) > 0:
                result = arrow_table.to_pylist()[0]
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
        user_id: uuid.UUID,
        property_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        expense_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List expenses with optional filters
        
        Args:
            user_id: User ID
            property_id: Optional property filter
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
            
            # Build filter
            filters = [EqualTo("created_by_user_id", str(user_id))]
            
            if property_id:
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
            row_filter = filters[0]
            for f in filters[1:]:
                row_filter = And(row_filter, f)
            
            # Query
            scan = table.scan(row_filter=row_filter)
            
            # Collect all results - scan.to_arrow() returns a Table
            arrow_table = scan.to_arrow()
            all_expenses = arrow_table.to_pylist()
            
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
        user_id: uuid.UUID,
        property_id: Optional[uuid.UUID] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get expense summary with yearly subtotals
        
        Args:
            user_id: User ID
            property_id: Optional property filter
            year: Optional year filter
        
        Returns:
            Summary dictionary with yearly subtotals
        """
        try:
            table = self._get_table()
            
            # Build filter
            filters = [EqualTo("created_by_user_id", str(user_id))]
            
            if property_id:
                filters.append(EqualTo("property_id", str(property_id)))
            
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
        user_id: uuid.UUID,
        expense_data: ExpenseUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        Update an expense
        
        Args:
            expense_id: Expense ID
            user_id: User ID for access control
            expense_data: Updated expense data
        
        Returns:
            Updated expense dictionary or None if not found
        """
        try:
            # Get existing expense
            existing = self.get_expense(expense_id, user_id)
            
            if not existing:
                return None
            
            # Update fields
            update_dict = expense_data.model_dump(exclude_unset=True)
            logger.info(f"[DEBUG] Update dict before processing: {update_dict}")
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
                    else:
                        existing[key] = value
            
            logger.info(f"[DEBUG] Date after update: {existing.get('date')} (type: {type(existing.get('date'))})")
            existing["updated_at"] = datetime.utcnow()
            
            # Ensure amount is Decimal (it may come back as float from Iceberg)
            if "amount" in existing and not isinstance(existing["amount"], Decimal):
                existing["amount"] = Decimal(str(existing["amount"]))
            
            # Get fresh table reference for writes to avoid lock issues
            table = self.catalog.load_table(f"{self.namespace}.{self.table_name}")
            
            table.delete(
                And(
                    EqualTo("id", str(expense_id)),
                    EqualTo("created_by_user_id", str(user_id))
                )
            )
            
            import pyarrow as pa
            schema = table.schema().as_arrow()
            arrow_table = pa.Table.from_pylist([existing], schema=schema)
            table.append(arrow_table)
            
            logger.info(f"Updated expense: {expense_id}")
            
            # Invalidate cache after write
            self._table_cache = None
            self._table_cache_time = None
            
            return existing
            
        except Exception as e:
            logger.error(f"Error updating expense: {e}", exc_info=True)
            return None
    
    def delete_expense(
        self,
        expense_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Delete an expense
        
        Args:
            expense_id: Expense ID
            user_id: User ID for access control
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify expense exists and belongs to user
            existing = self.get_expense(expense_id, user_id)
            
            if not existing:
                return False
            
            # Get fresh table reference for writes to avoid lock issues
            table = self.catalog.load_table(f"{self.namespace}.{self.table_name}")
            
            table.delete(
                And(
                    EqualTo("id", str(expense_id)),
                    EqualTo("created_by_user_id", str(user_id))
                )
            )
            
            logger.info(f"Deleted expense: {expense_id}")
            
            # Invalidate cache after write
            self._table_cache = None
            self._table_cache_time = None
            
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


def get_expense(expense_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Get an expense by ID"""
    return expense_service.get_expense(expense_id, user_id)


def list_expenses(
    user_id: uuid.UUID,
    property_id: Optional[uuid.UUID] = None,
    unit_id: Optional[uuid.UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    expense_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Dict[str, Any]], int]:
    """List expenses with filters"""
    return expense_service.list_expenses(
        user_id=user_id,
        property_id=property_id,
        unit_id=unit_id,
        start_date=start_date,
        end_date=end_date,
        expense_type=expense_type,
        skip=skip,
        limit=limit
    )


def get_expense_summary(
    user_id: uuid.UUID,
    property_id: Optional[uuid.UUID] = None,
    year: Optional[int] = None
) -> Dict[str, Any]:
    """Get expense summary with yearly subtotals"""
    return expense_service.get_expense_summary(
        user_id=user_id,
        property_id=property_id,
        year=year
    )


def update_expense(
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
    expense_data: ExpenseUpdate
) -> Optional[Dict[str, Any]]:
    """Update an expense"""
    return expense_service.update_expense(expense_id, user_id, expense_data)


def delete_expense(expense_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Delete an expense"""
    return expense_service.delete_expense(expense_id, user_id)
