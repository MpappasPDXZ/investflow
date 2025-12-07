"""
Financial Performance Service - Calculate and cache profit/loss for properties
"""
import logging
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
import pyarrow as pa
from pyiceberg.expressions import EqualTo, And
import pandas as pd

from app.core.iceberg import get_catalog, read_table, table_exists
from app.schemas.financial_performance import FinancialPerformanceSummary
from app.services.expense_service import ExpenseService

logger = logging.getLogger(__name__)


class FinancialPerformanceService:
    """Service for calculating and caching financial performance metrics"""
    
    def __init__(self):
        self.catalog = get_catalog()
        self.namespace = "investflow"
        self.table_name = "financial_performance"
        self.expense_service = ExpenseService()
        self._table_cache = None
        self._table_cache_time = None
        self._cache_ttl = 60  # Cache table reference for 60 seconds
    
    def _get_table(self, force_refresh: bool = False):
        """Get the financial_performance table with caching"""
        import time
        now = time.time()
        
        if not force_refresh and self._table_cache is not None and self._table_cache_time is not None:
            if now - self._table_cache_time < self._cache_ttl:
                return self._table_cache
        
        try:
            self._table_cache = self.catalog.load_table(f"{self.namespace}.{self.table_name}")
        except Exception:
            # Table doesn't exist, create it
            logger.info(f"Creating {self.namespace}.{self.table_name} table")
            schema = pa.schema([
                pa.field("id", pa.string(), nullable=False),
                pa.field("property_id", pa.string(), nullable=False),
                pa.field("unit_id", pa.string(), nullable=True),
                pa.field("ytd_rent", pa.decimal128(19, 4), nullable=False),
                pa.field("ytd_expenses", pa.decimal128(19, 4), nullable=False),
                pa.field("ytd_profit_loss", pa.decimal128(19, 4), nullable=False),
                pa.field("cumulative_rent", pa.decimal128(19, 4), nullable=False),
                pa.field("cumulative_expenses", pa.decimal128(19, 4), nullable=False),
                pa.field("cumulative_profit_loss", pa.decimal128(19, 4), nullable=False),
                pa.field("current_market_value", pa.decimal128(19, 4), nullable=True),
                pa.field("purchase_price", pa.decimal128(19, 4), nullable=False),
                pa.field("cash_on_cash", pa.decimal128(19, 4), nullable=True),
                pa.field("last_calculated_at", pa.date32(), nullable=False),
                pa.field("created_at", pa.timestamp("us"), nullable=False),
                pa.field("updated_at", pa.timestamp("us"), nullable=False),
            ])
            
            self._table_cache = self.catalog.create_table(
                identifier=f"{self.namespace}.{self.table_name}",
                schema=schema
            )
        
        self._table_cache_time = now
        return self._table_cache
    
    def calculate_financial_performance(
        self,
        property_id: UUID,
        user_id: UUID,
        unit_id: Optional[UUID] = None,
        purchase_price: Optional[Decimal] = None,
        current_market_value: Optional[Decimal] = None
    ) -> FinancialPerformanceSummary:
        """
        Calculate financial performance for a property or unit
        
        Excludes 'rehab' expenses from calculations as those are included in P&I financing
        """
        logger.info(f"[PERF] Calculating financial performance for property {property_id}, unit {unit_id}")
        
        # Get current year for YTD calculation
        current_year = datetime.now().year
        ytd_start = date(current_year, 1, 1)
        
        # Fetch all expenses for this property (excluding rehab)
        all_expenses = self.expense_service.list_expenses(
            user_id=user_id,
            property_id=str(property_id),
            limit=10000  # Get all
        )
        
        # Filter out rehab expenses
        expenses = [e for e in all_expenses['items'] if e.get('expense_type') != 'rehab']
        
        # Filter by unit if specified
        if unit_id:
            expenses = [e for e in expenses if e.get('unit_id') == str(unit_id)]
        
        # Fetch all rent payments using Iceberg directly
        rent_namespace = ("investflow",)
        rent_table_name = "rents"
        
        rent_payments = []
        if table_exists(rent_namespace, rent_table_name):
            rent_df = read_table(rent_namespace, rent_table_name)
            # Filter by property and user
            rent_df = rent_df[rent_df["property_id"] == str(property_id)]
            
            # Filter by unit if specified
            if unit_id:
                rent_df = rent_df[rent_df["unit_id"] == str(unit_id)]
            
            # Convert to list of dicts
            for _, row in rent_df.iterrows():
                rent_payments.append({
                    'amount': row['amount'],
                    'payment_date': row['payment_date']
                })
        
        # Calculate YTD
        ytd_rent = Decimal("0")
        ytd_expenses = Decimal("0")
        
        for rent in rent_payments:
            payment_date = rent['payment_date']
            if isinstance(payment_date, str):
                payment_date = datetime.fromisoformat(payment_date.split('T')[0]).date()
            if payment_date >= ytd_start:
                ytd_rent += Decimal(str(rent['amount']))
        
        for expense in expenses:
            expense_date = expense['date']
            if isinstance(expense_date, str):
                expense_date = datetime.fromisoformat(expense_date.split('T')[0]).date()
            if expense_date >= ytd_start and not expense.get('is_planned', False):
                ytd_expenses += Decimal(str(expense['amount']))
        
        ytd_profit_loss = ytd_rent - ytd_expenses
        
        # Calculate cumulative (all-time)
        cumulative_rent = sum(Decimal(str(r['amount'])) for r in rent_payments)
        cumulative_expenses = sum(
            Decimal(str(e['amount'])) for e in expenses 
            if not e.get('is_planned', False)
        )
        cumulative_profit_loss = cumulative_rent - cumulative_expenses
        
        # Calculate cash on cash
        cash_on_cash = None
        if purchase_price and current_market_value and purchase_price > 0:
            cash_on_cash = ((current_market_value - purchase_price) / purchase_price) * Decimal("100")
        
        logger.info(f"[PERF] Property {property_id}: YTD P/L={ytd_profit_loss}, Cumulative P/L={cumulative_profit_loss}")
        
        return FinancialPerformanceSummary(
            property_id=property_id,
            ytd_rent=ytd_rent,
            ytd_expenses=ytd_expenses,
            ytd_profit_loss=ytd_profit_loss,
            cumulative_rent=cumulative_rent,
            cumulative_expenses=cumulative_expenses,
            cumulative_profit_loss=cumulative_profit_loss,
            cash_on_cash=cash_on_cash,
            last_calculated_at=date.today()
        )
    
    def invalidate_cache(self, property_id: UUID, unit_id: Optional[UUID] = None):
        """
        Invalidate (delete) cached financial performance for a property/unit
        Called when expenses or rent are added/updated/deleted
        """
        logger.info(f"[PERF] Invalidating cache for property {property_id}, unit {unit_id}")
        
        try:
            table = self._get_table(force_refresh=True)
            
            # Delete existing records for this property/unit
            if unit_id:
                filter_expr = And(
                    EqualTo("property_id", str(property_id)),
                    EqualTo("unit_id", str(unit_id))
                )
            else:
                filter_expr = EqualTo("property_id", str(property_id))
            
            table.delete(filter_expr)
            logger.info(f"[PERF] Cache invalidated for property {property_id}")
            
            # Invalidate table cache
            self._table_cache = None
            
        except Exception as e:
            logger.error(f"[PERF] Error invalidating cache: {e}", exc_info=True)


# Singleton instance
financial_performance_service = FinancialPerformanceService()

