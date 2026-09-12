"""Expense service for managing expenses in Iceberg or Postgres"""
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from decimal import Decimal
import pandas as pd
from pyiceberg.expressions import EqualTo
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.core.iceberg import load_table, read_table, append_data, upsert_data_with_schema_cast, uses_postgres
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "expenses"


def _none_if_null(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if value == "" or value == "None" or value == "nan" or value == "NaT":
        return None
    return value


def _clean_expense_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize pandas/Iceberg row for API consumers (nan-safe UUIDs/strings)."""
    result = dict(row)
    for key in ("unit_id", "document_storage_id", "vendor", "notes", "expense_category", "tax_category"):
        if key in result:
            result[key] = _none_if_null(result.get(key))

    for key in ("unit_id", "document_storage_id", "id", "property_id"):
        val = result.get(key)
        if val is not None and not isinstance(val, uuid.UUID):
            try:
                result[key] = uuid.UUID(str(val)) if key in ("unit_id", "document_storage_id") else str(val)
            except (ValueError, TypeError):
                if key in ("unit_id", "document_storage_id"):
                    result[key] = None

    # Keep id/property_id as strings for write paths; UUID for unit/doc is OK for response
    if "id" in result and result["id"] is not None:
        result["id"] = str(result["id"]) if not isinstance(result["id"], uuid.UUID) else result["id"]
    if "property_id" in result and result["property_id"] is not None:
        result["property_id"] = str(result["property_id"]) if not isinstance(result["property_id"], uuid.UUID) else result["property_id"]

    if "has_receipt" in result:
        if result["has_receipt"] is None or (isinstance(result["has_receipt"], float) and pd.isna(result["has_receipt"])):
            result["has_receipt"] = result.get("document_storage_id") is not None
        else:
            result["has_receipt"] = bool(result["has_receipt"])

    if "amount" in result and result["amount"] is not None and not isinstance(result["amount"], Decimal):
        try:
            if pd.isna(result["amount"]):
                result["amount"] = Decimal("0")
            else:
                result["amount"] = Decimal(str(result["amount"]))
        except Exception:
            result["amount"] = Decimal(str(result["amount"]))

    # date32 / pandas NaT breaks Pydantic date fields
    d = result.get("date")
    if d is None or (not isinstance(d, date)) or (isinstance(d, float) and pd.isna(d)):
        try:
            if d is not None and pd.isna(d):
                d = None
        except Exception:
            pass
        if d is None:
            created = result.get("created_at")
            if created is not None and not (isinstance(created, float) and pd.isna(created)):
                try:
                    d = pd.Timestamp(created).date()
                except Exception:
                    d = date(1970, 1, 1)
            else:
                d = date(1970, 1, 1)
        elif hasattr(d, "date") and not isinstance(d, date):
            d = d.date()
        result["date"] = d
    elif hasattr(d, "date") and not isinstance(d, date):
        result["date"] = d.date()

    for ts_key in ("created_at", "updated_at"):
        ts = result.get(ts_key)
        if ts is not None:
            try:
                if pd.isna(ts):
                    result[ts_key] = datetime.utcnow()
                else:
                    result[ts_key] = pd.Timestamp(ts).to_pydatetime()
            except Exception:
                pass

    return result


class ExpenseService:
    """Service for managing expenses in Iceberg or Postgres"""

    def __init__(self):
        self.namespace = NAMESPACE
        self.table_name = TABLE_NAME
        self._table_cache = None
        self._table_cache_time = None
        self._cache_ttl = 60
        self._financial_performance_service = None

    def _get_financial_performance_service(self):
        if self._financial_performance_service is None:
            from app.services.financial_performance_service import financial_performance_service
            self._financial_performance_service = financial_performance_service
        return self._financial_performance_service

    def _get_table(self, use_cache=True):
        """Get the expenses table with caching (migration-aware)."""
        import time
        now = time.time()
        if use_cache and self._table_cache is not None and self._table_cache_time is not None:
            if now - self._table_cache_time < self._cache_ttl:
                return self._table_cache
        self._table_cache = load_table(self.namespace, self.table_name)
        self._table_cache_time = now
        return self._table_cache

    def _read_df(self) -> pd.DataFrame:
        return read_table(self.namespace, self.table_name)

    def _invalidate_table_cache(self):
        self._table_cache = None
        self._table_cache_time = None

    def create_expense(
        self,
        user_id: uuid.UUID,
        expense_data: ExpenseCreate
    ) -> Dict[str, Any]:
        try:
            expense_id = str(uuid.uuid4())
            now = datetime.utcnow()
            has_receipt = expense_data.document_storage_id is not None

            record = {
                "id": expense_id,
                "property_id": str(expense_data.property_id),
                "unit_id": str(expense_data.unit_id) if expense_data.unit_id else None,
                "description": expense_data.description,
                "vendor": expense_data.vendor,
                "expense_type": expense_data.expense_type.value,
                "expense_category": expense_data.expense_category.value if expense_data.expense_category else None,
                "tax_category": expense_data.tax_category.value if expense_data.tax_category else None,
                "document_storage_id": str(expense_data.document_storage_id) if expense_data.document_storage_id else None,
                "notes": expense_data.notes,
                "amount": Decimal(str(expense_data.amount)),
                "date": expense_data.date,
                "has_receipt": has_receipt,
                "created_at": now,
                "updated_at": now
            }

            df = pd.DataFrame([record])
            append_data(self.namespace, self.table_name, df)
            self._invalidate_table_cache()
            logger.info(f"Created expense: {expense_id}")

            try:
                import asyncio
                fp_service = self._get_financial_performance_service()
                asyncio.create_task(
                    asyncio.to_thread(
                        fp_service.invalidate_cache,
                        expense_data.property_id,
                        user_id,
                        expense_data.unit_id
                    )
                )
            except Exception as cache_err:
                logger.warning(f"Failed to schedule financial performance cache invalidation: {cache_err}")

            return record

        except Exception as e:
            logger.error(f"Error creating expense: {e}", exc_info=True)
            raise

    def get_expense(self, expense_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        try:
            df = self._read_df()
            if df.empty or "id" not in df.columns:
                return None
            match = df[df["id"].astype(str) == str(expense_id)]
            if match.empty:
                return None
            return _clean_expense_row(match.iloc[0].to_dict())
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
        try:
            if not property_id:
                return [], 0

            df = self._read_df()
            if df.empty:
                return [], 0

            filtered = df[df["property_id"].astype(str) == str(property_id)]
            if unit_id:
                filtered = filtered[filtered["unit_id"].astype(str) == str(unit_id)]
            if start_date is not None and "date" in filtered.columns:
                filtered = filtered[pd.to_datetime(filtered["date"]).dt.date >= start_date]
            if end_date is not None and "date" in filtered.columns:
                filtered = filtered[pd.to_datetime(filtered["date"]).dt.date <= end_date]
            if expense_type:
                filtered = filtered[filtered["expense_type"].astype(str) == expense_type]

            all_expenses = [_clean_expense_row(r) for r in filtered.to_dict(orient="records")]

            # Deduplicate by id (append history); keep latest updated_at
            expense_dict: Dict[str, Dict[str, Any]] = {}
            for expense in all_expenses:
                eid = str(expense.get("id")) if expense.get("id") is not None else None
                if not eid:
                    continue
                if eid not in expense_dict:
                    expense_dict[eid] = expense
                else:
                    existing_updated = expense_dict[eid].get("updated_at")
                    current_updated = expense.get("updated_at")
                    if current_updated and (not existing_updated or current_updated > existing_updated):
                        expense_dict[eid] = expense

            all_expenses = list(expense_dict.values())
            all_expenses.sort(key=lambda x: x.get("date") or date.min, reverse=True)
            total = len(all_expenses)
            return all_expenses[skip:skip + limit], total

        except Exception as e:
            logger.error(f"Error listing expenses: {e}", exc_info=True)
            return [], 0

    def get_expense_summary(
        self,
        property_id: uuid.UUID,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            expenses, _ = self.list_expenses(property_id=property_id, skip=0, limit=100_000)

            yearly_totals: Dict[int, Dict[str, Any]] = {}
            type_totals: Dict[str, float] = {}
            tax_category_totals: Dict[str, float] = {}

            for expense in expenses:
                expense_date = expense.get("date")
                expense_year = expense_date.year if hasattr(expense_date, "year") else None
                if not expense_year:
                    continue
                if year and expense_year != year:
                    continue

                amount = float(expense.get("amount") or 0)
                exp_type = expense.get("expense_type") or "other"
                tax_cat = expense.get("tax_category") or "other"

                if expense_year not in yearly_totals:
                    yearly_totals[expense_year] = {
                        "year": expense_year,
                        "total": 0.0,
                        "count": 0,
                        "by_type": {},
                        "by_tax_category": {},
                    }
                yt = yearly_totals[expense_year]
                yt["total"] += amount
                yt["count"] += 1
                yt["by_type"][exp_type] = yt["by_type"].get(exp_type, 0.0) + amount
                yt["by_tax_category"][tax_cat] = yt["by_tax_category"].get(tax_cat, 0.0) + amount

                type_totals[exp_type] = type_totals.get(exp_type, 0.0) + amount
                tax_category_totals[tax_cat] = tax_category_totals.get(tax_cat, 0.0) + amount

            yearly_list = sorted(yearly_totals.values(), key=lambda x: x["year"], reverse=True)
            return {
                "yearly_totals": yearly_list,
                "type_totals": type_totals,
                "tax_category_totals": tax_category_totals,
                "grand_total": sum(y["total"] for y in yearly_list),
                "total_count": sum(y["count"] for y in yearly_list),
            }
        except Exception as e:
            logger.error(f"Error getting expense summary: {e}", exc_info=True)
            return {
                "yearly_totals": [],
                "type_totals": {},
                "tax_category_totals": {},
                "grand_total": 0,
                "total_count": 0,
            }

    def update_expense(
        self,
        expense_id: uuid.UUID,
        expense_data: ExpenseUpdate
    ) -> Optional[Dict[str, Any]]:
        try:
            existing = self.get_expense(expense_id)
            if not existing:
                return None

            update_dict = expense_data.model_dump(exclude_unset=True)
            document_storage_id_updated = "document_storage_id" in update_dict

            for key, value in update_dict.items():
                if value is not None:
                    if key in ["property_id", "unit_id", "document_storage_id"] and value:
                        existing[key] = str(value)
                    elif key in ["expense_type", "expense_category", "tax_category"] and value:
                        existing[key] = value.value
                    elif key == "amount" and value:
                        existing[key] = Decimal(str(value))
                    elif key == "date" and value:
                        existing[key] = value
                    elif key == "has_receipt":
                        existing[key] = value
                    else:
                        existing[key] = value
                elif key == "document_storage_id":
                    existing[key] = None

            if document_storage_id_updated and "has_receipt" not in update_dict:
                existing["has_receipt"] = _none_if_null(existing.get("document_storage_id")) is not None
            if "has_receipt" not in existing:
                existing["has_receipt"] = _none_if_null(existing.get("document_storage_id")) is not None

            existing["updated_at"] = datetime.utcnow()
            if "amount" in existing and not isinstance(existing["amount"], Decimal):
                existing["amount"] = Decimal(str(existing["amount"]))

            existing_for_df = existing.copy()
            for field in ("id", "property_id", "unit_id", "document_storage_id"):
                value = existing_for_df.get(field)
                if value is None:
                    existing_for_df[field] = None
                elif isinstance(value, uuid.UUID):
                    existing_for_df[field] = str(value)
                elif value in ("None", ""):
                    existing_for_df[field] = None
                else:
                    existing_for_df[field] = str(value)

            if existing_for_df.get("date") and isinstance(existing_for_df["date"], datetime):
                existing_for_df["date"] = existing_for_df["date"].date()

            ordered_dict = {
                "id": existing_for_df.get("id"),
                "property_id": existing_for_df.get("property_id"),
                "unit_id": existing_for_df.get("unit_id"),
                "description": existing_for_df.get("description"),
                "vendor": existing_for_df.get("vendor"),
                "expense_type": existing_for_df.get("expense_type"),
                "expense_category": existing_for_df.get("expense_category"),
                "tax_category": existing_for_df.get("tax_category"),
                "document_storage_id": existing_for_df.get("document_storage_id"),
                "notes": _none_if_null(existing_for_df.get("notes")),
                "amount": existing_for_df.get("amount"),
                "date": existing_for_df.get("date"),
                "has_receipt": existing_for_df.get("has_receipt"),
                "created_at": existing_for_df.get("created_at"),
                "updated_at": existing_for_df.get("updated_at"),
            }
            df = pd.DataFrame([ordered_dict])

            try:
                table = self._get_table(use_cache=False)
                table.delete(EqualTo("id", str(expense_id)))
                append_data(self.namespace, self.table_name, df)
            except Exception as delete_error:
                logger.warning(f"[UPDATE] Error during delete-append: {delete_error}, trying upsert instead")
                upsert_data_with_schema_cast(
                    namespace=self.namespace,
                    table_name=self.table_name,
                    data=df,
                    join_cols=["id"],
                )

            self._invalidate_table_cache()
            logger.info(f"Updated expense: {expense_id}")

            try:
                fp_service = self._get_financial_performance_service()
                fp_service.invalidate_cache(
                    property_id=uuid.UUID(str(existing["property_id"])),
                    user_id=None,
                    unit_id=uuid.UUID(str(existing["unit_id"])) if _none_if_null(existing.get("unit_id")) else None,
                )
            except Exception as cache_err:
                logger.warning(f"Failed to invalidate financial performance cache: {cache_err}")

            return _clean_expense_row(existing)

        except Exception as e:
            logger.error(f"Error updating expense: {e}", exc_info=True)
            return None

    def delete_expense(self, expense_id: uuid.UUID) -> bool:
        try:
            existing = self.get_expense(expense_id)
            if not existing:
                return False

            table = self._get_table(use_cache=False)
            table.delete(EqualTo("id", str(expense_id)))
            self._invalidate_table_cache()
            logger.info(f"Deleted expense: {expense_id}")

            try:
                fp_service = self._get_financial_performance_service()
                fp_service.invalidate_cache(
                    property_id=uuid.UUID(str(existing["property_id"])),
                    user_id=None,
                    unit_id=uuid.UUID(str(existing["unit_id"])) if _none_if_null(existing.get("unit_id")) else None,
                )
            except Exception as cache_err:
                logger.warning(f"Failed to invalidate financial performance cache: {cache_err}")

            return True
        except Exception as e:
            logger.error(f"Error deleting expense: {e}", exc_info=True)
            return False


# Global instance
expense_service = ExpenseService()


def create_expense(user_id: uuid.UUID, expense_data: ExpenseCreate) -> Dict[str, Any]:
    return expense_service.create_expense(user_id, expense_data)


def get_expense(expense_id: uuid.UUID) -> Optional[Dict[str, Any]]:
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
    return expense_service.list_expenses(
        property_id=property_id,
        unit_id=unit_id,
        start_date=start_date,
        end_date=end_date,
        expense_type=expense_type,
        skip=skip,
        limit=limit,
    )


def get_expense_summary(
    property_id: uuid.UUID,
    year: Optional[int] = None
) -> Dict[str, Any]:
    return expense_service.get_expense_summary(property_id=property_id, year=year)


def update_expense(
    expense_id: uuid.UUID,
    expense_data: ExpenseUpdate
) -> Optional[Dict[str, Any]]:
    return expense_service.update_expense(expense_id, expense_data)


def delete_expense(expense_id: uuid.UUID) -> bool:
    return expense_service.delete_expense(expense_id)
