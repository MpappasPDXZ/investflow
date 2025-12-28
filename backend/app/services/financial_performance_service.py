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

# Import cache service (lazy to avoid circular imports)
_fp_cache = None


def get_fp_cache():
    """Lazy load financial performance cache"""
    global _fp_cache
    if _fp_cache is None:
        from app.services.financial_performance_cache_service import financial_performance_cache
        _fp_cache = financial_performance_cache
    return _fp_cache


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
        cash_invested: Optional[Decimal] = None,
        down_payment: Optional[Decimal] = None
    ) -> FinancialPerformanceSummary:
        """
        Calculate financial performance for a property or unit
        
        Calculates fresh from Iceberg tables (no caching)
        
        Excludes 'rehab' expenses from calculations as those are included in P&I financing
        """
        logger.info(f"[PERF] Calculating financial performance for property {property_id}, unit {unit_id}")
        
        # DISABLED: Cache check removed for real-time accuracy
        # Always calculate fresh from Iceberg tables
        
        # Get current year for YTD calculation
        current_year = datetime.now().year
        ytd_start = date(current_year, 1, 1)
        
        # Fetch all expenses for this property (excluding rehab)
        all_expenses, _ = self.expense_service.list_expenses(
            user_id=user_id,
            property_id=str(property_id),
            limit=10000  # Get all
        )
        
        # Filter out rehab expenses
        expenses = [e for e in all_expenses if e.get('expense_type') != 'rehab']
        
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
                    'payment_date': row['payment_date'],
                    'is_non_irs_revenue': row.get('is_non_irs_revenue', False) if pd.notna(row.get('is_non_irs_revenue')) else False
                })
        
        # Calculate YTD with breakdowns
        ytd_rent = Decimal("0")  # IRS revenue only (excludes deposits)
        ytd_total_revenue = Decimal("0")  # Total revenue (includes deposits)
        ytd_expenses = Decimal("0")
        ytd_breakdown = {
            'piti': Decimal("0"),
            'utilities': Decimal("0"),
            'maintenance': Decimal("0"),
            'capex': Decimal("0"),
            'insurance': Decimal("0"),
            'property_management': Decimal("0"),
            'other': Decimal("0")
        }
        
        for rent in rent_payments:
            payment_date = rent['payment_date']
            # Handle pandas Timestamp, string, or date objects
            if isinstance(payment_date, pd.Timestamp):
                payment_date = payment_date.date()
            elif isinstance(payment_date, str):
                payment_date = datetime.fromisoformat(payment_date.split('T')[0]).date()
            elif isinstance(payment_date, datetime):
                payment_date = payment_date.date()
            # If it's already a date, use it as-is
            
            if payment_date >= ytd_start:
                # Add to total revenue (all rent including deposits)
                ytd_total_revenue += Decimal(str(rent['amount']))
                
                # Only add to IRS revenue if it's not non-IRS revenue (deposits)
                is_non_irs = rent.get('is_non_irs_revenue', False)
                if not is_non_irs:
                    ytd_rent += Decimal(str(rent['amount']))
        
        for expense in expenses:
            expense_date = expense['date']
            if isinstance(expense_date, str):
                expense_date = datetime.fromisoformat(expense_date.split('T')[0]).date()
            # Exclude rehab expenses and planned expenses from YTD
            exp_type = expense.get('expense_type', 'other')
            if expense_date >= ytd_start and not expense.get('is_planned', False) and exp_type != 'rehab':
                amount = Decimal(str(expense['amount']))
                ytd_expenses += amount
                
                # Categorize by expense_type
                if exp_type == 'pandi':
                    ytd_breakdown['piti'] += amount
                elif exp_type == 'utilities':
                    ytd_breakdown['utilities'] += amount
                elif exp_type == 'maintenance':
                    ytd_breakdown['maintenance'] += amount
                elif exp_type == 'capex':
                    ytd_breakdown['capex'] += amount
                elif exp_type == 'insurance':
                    ytd_breakdown['insurance'] += amount
                elif exp_type == 'property_management':
                    ytd_breakdown['property_management'] += amount
                else:
                    ytd_breakdown['other'] += amount
        
        ytd_profit_loss = ytd_rent - ytd_expenses
        
        # Calculate cumulative (all-time) with breakdowns
        # Exclude non-IRS revenue (deposits) from cumulative rent as well
        cumulative_rent = sum(
            Decimal(str(r['amount'])) 
            for r in rent_payments 
            if not r.get('is_non_irs_revenue', False)
        )
        cumulative_expenses = Decimal("0")
        cumulative_breakdown = {
            'piti': Decimal("0"),
            'utilities': Decimal("0"),
            'maintenance': Decimal("0"),
            'capex': Decimal("0"),
            'insurance': Decimal("0"),
            'property_management': Decimal("0"),
            'other': Decimal("0")
        }
        
        for expense in expenses:
            exp_type = expense.get('expense_type', 'other')
            # Exclude rehab expenses and planned expenses from cumulative
            if not expense.get('is_planned', False) and exp_type != 'rehab':
                amount = Decimal(str(expense['amount']))
                cumulative_expenses += amount
                
                if exp_type == 'pandi':
                    cumulative_breakdown['piti'] += amount
                elif exp_type == 'utilities':
                    cumulative_breakdown['utilities'] += amount
                elif exp_type == 'maintenance':
                    cumulative_breakdown['maintenance'] += amount
                elif exp_type == 'capex':
                    cumulative_breakdown['capex'] += amount
                elif exp_type == 'insurance':
                    cumulative_breakdown['insurance'] += amount
                elif exp_type == 'property_management':
                    cumulative_breakdown['property_management'] += amount
                else:
                    cumulative_breakdown['other'] += amount
        
        cumulative_profit_loss = cumulative_rent - cumulative_expenses
        
        # Calculate cash on cash return
        # Formula: (Annual Net Income) / (Total Cash Invested)
        # Use manual cash_invested if available, otherwise fallback to down_payment
        cash_on_cash = None
        investment_amount = None
        
        if cash_invested and cash_invested > 0:
            investment_amount = cash_invested
        elif down_payment and down_payment > 0:
            investment_amount = down_payment
        
        if investment_amount and investment_amount > 0:
            # Annualized profit/loss
            days_ytd = (date.today() - ytd_start).days
            if days_ytd > 0:
                annual_profit_loss = (ytd_profit_loss / Decimal(str(days_ytd))) * Decimal("365")
            else:
                annual_profit_loss = ytd_profit_loss
            
            cash_on_cash = (annual_profit_loss / investment_amount) * Decimal("100")
        
        logger.info(f"[PERF] Property {property_id}: YTD P/L={ytd_profit_loss}, Cumulative P/L={cumulative_profit_loss}")
        
        return FinancialPerformanceSummary(
            property_id=property_id,
            ytd_total_revenue=ytd_total_revenue,
            ytd_rent=ytd_rent,  # IRS revenue only
            ytd_expenses=ytd_expenses,
            ytd_profit_loss=ytd_profit_loss,
            ytd_piti=ytd_breakdown['piti'],
            ytd_utilities=ytd_breakdown['utilities'],
            ytd_maintenance=ytd_breakdown['maintenance'],
            ytd_capex=ytd_breakdown['capex'],
            ytd_insurance=ytd_breakdown['insurance'],
            ytd_property_management=ytd_breakdown['property_management'],
            ytd_other=ytd_breakdown['other'],
            cumulative_rent=cumulative_rent,
            cumulative_expenses=cumulative_expenses,
            cumulative_profit_loss=cumulative_profit_loss,
            cumulative_piti=cumulative_breakdown['piti'],
            cumulative_utilities=cumulative_breakdown['utilities'],
            cumulative_maintenance=cumulative_breakdown['maintenance'],
            cumulative_capex=cumulative_breakdown['capex'],
            cumulative_insurance=cumulative_breakdown['insurance'],
            cumulative_property_management=cumulative_breakdown['property_management'],
            cumulative_other=cumulative_breakdown['other'],
            cash_on_cash=cash_on_cash,
            last_calculated_at=date.today()
        )
    
    def invalidate_cache(self, property_id: UUID, user_id: UUID, unit_id: Optional[UUID] = None):
        """
        Invalidate and recalculate cached financial performance for a property/unit.
        Called when expenses or rent are added/updated/deleted.
        
        This triggers an ASYNC recalculation (non-blocking) that updates the ADLS parquet cache.
        """
        logger.info(f"[PERF] Invalidating cache for property {property_id}, unit {unit_id}")
        
        try:
            # Trigger async recalculation in ADLS cache
            fp_cache = get_fp_cache()
            fp_cache.update_performance_async(property_id, user_id, unit_id)
            logger.info(f"[PERF] Async recalculation queued for property {property_id}")
            
        except Exception as e:
            logger.error(f"[PERF] Error invalidating cache: {e}", exc_info=True)


# Singleton instance
financial_performance_service = FinancialPerformanceService()

