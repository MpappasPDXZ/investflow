"""
Financial Performance CDC Cache stored as Parquet in ADLS.

This service provides FAST lookups for financial performance (P&L):
- Rent collected (YTD and cumulative)
- Expenses by category (excluding rehab)  
- Profit/Loss calculations

The cache is stored as Parquet files in ADLS and computed asynchronously.
Updates happen in parallel when expenses or rent are added (non-blocking).
"""
import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Optional, Dict, List, Any
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from azure.storage.blob import BlobServiceClient
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = ("investflow",)


class FinancialPerformanceCacheService:
    """
    CDC cache for financial performance (P&L).
    Stores: property_id → financial metrics as Parquet in ADLS.
    Provides fast O(1) lookups for dashboard display.
    """
    
    # ADLS path for financial performance cache
    FP_CACHE_PATH = "cdc/financial_performance/financial_performance_current.parquet"
    
    @property
    def cache_container(self) -> str:
        """Get the container name for CDC cache (configurable)"""
        if settings.CDC_CACHE_CONTAINER_NAME:
            return settings.CDC_CACHE_CONTAINER_NAME
        return settings.AZURE_STORAGE_CONTAINER_NAME or "documents"
    
    def __init__(self):
        # In-memory cache: property_id → financial performance dict
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_loaded_at: Optional[datetime] = None
        self._initialized = False
        
        # Blob client (lazy init)
        self._blob_service: Optional[BlobServiceClient] = None
    
    def _get_blob_service(self) -> Optional[BlobServiceClient]:
        """Get or create Azure Blob client (lazy initialization)"""
        if self._blob_service is not None:
            return self._blob_service
        
        try:
            if settings.AZURE_STORAGE_CONNECTION_STRING:
                self._blob_service = BlobServiceClient.from_connection_string(
                    settings.AZURE_STORAGE_CONNECTION_STRING
                )
            elif settings.AZURE_STORAGE_ACCOUNT_NAME and settings.AZURE_STORAGE_ACCOUNT_KEY:
                conn_str = (
                    f"DefaultEndpointsProtocol=https;"
                    f"AccountName={settings.AZURE_STORAGE_ACCOUNT_NAME};"
                    f"AccountKey={settings.AZURE_STORAGE_ACCOUNT_KEY};"
                    f"EndpointSuffix=core.windows.net"
                )
                self._blob_service = BlobServiceClient.from_connection_string(conn_str)
            else:
                logger.warning("Azure Storage not configured, financial performance cache will compute on-demand")
                return None
            
            return self._blob_service
        except Exception as e:
            logger.error(f"Failed to initialize blob service: {e}")
            return None
    
    def initialize(self) -> bool:
        """Initialize the cache on startup - load from ADLS"""
        if self._initialized:
            return True
        
        logger.info("Initializing financial performance cache...")
        
        if self._load_from_adls():
            logger.info(f"Financial performance cache loaded: {len(self._cache)} properties")
            self._initialized = True
            return True
        
        logger.info("Financial performance cache empty or not found, will compute on-demand")
        self._initialized = True
        return True
    
    def _load_from_adls(self) -> bool:
        """Load parquet cache from ADLS into memory"""
        blob_service = self._get_blob_service()
        if blob_service is None:
            return False
        
        try:
            df = self._read_parquet_from_adls(self.FP_CACHE_PATH)
            if df is None or df.empty:
                return False
            
            # Rebuild in-memory cache
            self._rebuild_cache(df)
            self._cache_loaded_at = datetime.utcnow()
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading from ADLS: {e}")
            return False
    
    def _read_parquet_from_adls(self, blob_path: str) -> Optional[pd.DataFrame]:
        """Read a parquet file from ADLS"""
        blob_service = self._get_blob_service()
        if blob_service is None:
            return None
        
        try:
            blob_client = blob_service.get_blob_client(
                container=self.cache_container,
                blob=blob_path
            )
            
            if not blob_client.exists():
                logger.debug(f"Cache file does not exist: {blob_path}")
                return None
            
            # Download and read parquet
            stream = io.BytesIO()
            blob_client.download_blob().readinto(stream)
            stream.seek(0)
            
            df = pq.read_table(stream).to_pandas()
            logger.debug(f"Loaded {len(df)} rows from {blob_path}")
            return df
            
        except Exception as e:
            logger.error(f"Error reading parquet from ADLS ({blob_path}): {e}")
            return None
    
    def _save_parquet_to_adls(self, df: pd.DataFrame, blob_path: str) -> bool:
        """Save a DataFrame as parquet to ADLS"""
        blob_service = self._get_blob_service()
        if blob_service is None:
            logger.warning("No blob service, skipping ADLS persist")
            return False
        
        try:
            # Ensure container exists
            container_client = blob_service.get_container_client(self.cache_container)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {self.cache_container}")
            
            # Add CDC timestamp
            df = df.copy()
            df["_cdc_timestamp"] = pd.Timestamp.now()
            
            # Convert timestamps to microseconds (Parquet requirement)
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].astype('datetime64[us]')
            
            # Convert to parquet bytes
            table = pa.Table.from_pandas(df, preserve_index=False)
            stream = io.BytesIO()
            pq.write_table(table, stream)
            stream.seek(0)
            
            # Upload to ADLS
            blob_client = blob_service.get_blob_client(
                container=self.cache_container,
                blob=blob_path
            )
            blob_client.upload_blob(stream, overwrite=True)
            
            logger.debug(f"Saved {len(df)} rows to {blob_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving parquet to ADLS ({blob_path}): {e}")
            return False
    
    def _rebuild_cache(self, df: pd.DataFrame):
        """Rebuild in-memory cache from DataFrame"""
        self._cache = {}
        
        for _, row in df.iterrows():
            property_id = row.get("property_id")
            unit_id = row.get("unit_id")
            
            # Create cache key
            if unit_id and not pd.isna(unit_id):
                cache_key = f"{property_id}:{unit_id}"
            else:
                cache_key = property_id
            
            # Store performance dict
            perf_dict = row.to_dict()
            perf_dict.pop("_cdc_timestamp", None)
            self._cache[cache_key] = perf_dict
        
        logger.debug(f"Rebuilt cache: {len(self._cache)} entries")
    
    def get_performance(self, property_id: UUID, unit_id: Optional[UUID] = None) -> Optional[Dict[str, Any]]:
        """
        Get financial performance from cache (fast O(1) lookup).
        Returns None if not in cache (should trigger background recalculation).
        """
        if not self._initialized:
            self.initialize()
        
        # Build cache key
        if unit_id:
            cache_key = f"{str(property_id)}:{str(unit_id)}"
        else:
            cache_key = str(property_id)
        
        return self._cache.get(cache_key)
    
    def update_performance_async(self, property_id: UUID, user_id: UUID, unit_id: Optional[UUID] = None):
        """
        Update financial performance cache asynchronously (non-blocking).
        Called after expense or rent is added/updated/deleted.
        This should NOT slow down the calling API.
        """
        try:
            import threading
            
            # Run calculation in background thread
            thread = threading.Thread(
                target=self._recalculate_and_persist,
                args=(property_id, user_id, unit_id),
                daemon=True
            )
            thread.start()
            
            logger.debug(f"Started background calculation for property {property_id}")
            
        except Exception as e:
            logger.error(f"Error starting async update: {e}")
    
    def _recalculate_and_persist(self, property_id: UUID, user_id: UUID, unit_id: Optional[UUID] = None):
        """
        Recalculate financial performance and persist to ADLS.
        Runs in background thread.
        """
        try:
            # Import here to avoid circular dependency
            from app.services.expense_service import ExpenseService
            from app.core.iceberg import read_table, table_exists
            
            logger.info(f"[FP-CACHE] Recalculating for property {property_id}, unit {unit_id}")
            
            # Get property details for purchase price
            properties_df = read_table(NAMESPACE, "properties")
            property_df = properties_df[properties_df["id"] == str(property_id)]
            
            if len(property_df) == 0:
                logger.warning(f"Property {property_id} not found")
                return
            
            property_dict = property_df.iloc[0].to_dict()
            purchase_price = property_dict.get('purchase_price')
            current_market_value = property_dict.get('current_market_value')
            cash_invested = property_dict.get('cash_invested')  # Manual entry preferred
            down_payment = property_dict.get('down_payment')
            
            # Get current year
            current_year = datetime.now().year
            ytd_start = date(current_year, 1, 1)
            
            # Fetch expenses (excluding rehab)
            expense_service = ExpenseService()
            all_expenses = expense_service.list_expenses(
                user_id=user_id,
                property_id=property_id,
                limit=10000
            )[0]  # Returns (items, total)
            
            expenses = [e for e in all_expenses if e.get('expense_type') != 'rehab']
            
            # Filter by unit if specified
            if unit_id:
                expenses = [e for e in expenses if e.get('unit_id') == str(unit_id)]
            
            # Fetch rent payments
            rent_payments = []
            if table_exists(NAMESPACE, "rents"):
                rent_df = read_table(NAMESPACE, "rents")
                rent_df = rent_df[rent_df["property_id"] == str(property_id)]
                
                if unit_id:
                    rent_df = rent_df[rent_df["unit_id"] == str(unit_id)]
                
                for _, row in rent_df.iterrows():
                    rent_payments.append({
                        'amount': row['amount'],
                        'payment_date': row['payment_date'],
                        'is_non_irs_revenue': row.get('is_non_irs_revenue', False) if pd.notna(row.get('is_non_irs_revenue')) else False
                    })
            
            # Calculate YTD metrics
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
                exp_type = expense.get('expense_type', 'other')
                # Exclude rehab expenses and planned expenses from YTD
                if expense_date >= ytd_start and not expense.get('is_planned', False) and exp_type != 'rehab':
                    amount = Decimal(str(expense['amount']))
                    ytd_expenses += amount
                    
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
            
            # Calculate cumulative metrics
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
                investment_amount = Decimal(str(cash_invested))
            elif down_payment and down_payment > 0:
                investment_amount = Decimal(str(down_payment))
            
            if investment_amount and investment_amount > 0:
                # Annualized profit/loss
                from datetime import date
                days_ytd = (date.today() - ytd_start).days
                if days_ytd > 0:
                    annual_profit_loss = (ytd_profit_loss / Decimal(str(days_ytd))) * Decimal("365")
                else:
                    annual_profit_loss = ytd_profit_loss
                
                cash_on_cash = float((annual_profit_loss / investment_amount) * Decimal("100"))
            
            # Create performance record
            perf_record = {
                "property_id": str(property_id),
                "unit_id": str(unit_id) if unit_id else None,
                "ytd_total_revenue": float(ytd_total_revenue),
                "ytd_rent": float(ytd_rent),  # IRS revenue only
                "ytd_expenses": float(ytd_expenses),
                "ytd_profit_loss": float(ytd_profit_loss),
                "ytd_piti": float(ytd_breakdown['piti']),
                "ytd_utilities": float(ytd_breakdown['utilities']),
                "ytd_maintenance": float(ytd_breakdown['maintenance']),
                "ytd_capex": float(ytd_breakdown['capex']),
                "ytd_insurance": float(ytd_breakdown['insurance']),
                "ytd_property_management": float(ytd_breakdown['property_management']),
                "ytd_other": float(ytd_breakdown['other']),
                "cumulative_rent": float(cumulative_rent),
                "cumulative_expenses": float(cumulative_expenses),
                "cumulative_profit_loss": float(cumulative_profit_loss),
                "cumulative_piti": float(cumulative_breakdown['piti']),
                "cumulative_utilities": float(cumulative_breakdown['utilities']),
                "cumulative_maintenance": float(cumulative_breakdown['maintenance']),
                "cumulative_capex": float(cumulative_breakdown['capex']),
                "cumulative_insurance": float(cumulative_breakdown['insurance']),
                "cumulative_property_management": float(cumulative_breakdown['property_management']),
                "cumulative_other": float(cumulative_breakdown['other']),
                "cash_on_cash": cash_on_cash,
                "last_calculated_at": pd.Timestamp.now(),
            }
            
            # Update in-memory cache
            cache_key = f"{str(property_id)}:{str(unit_id)}" if unit_id else str(property_id)
            self._cache[cache_key] = perf_record
            
            # Persist entire cache to ADLS
            self._persist_cache()
            
            logger.info(f"[FP-CACHE] Updated property {property_id}, YTD P/L={ytd_profit_loss}")
            
        except Exception as e:
            logger.error(f"Error recalculating performance: {e}", exc_info=True)
    
    def _persist_cache(self):
        """Persist entire cache to ADLS as parquet"""
        try:
            if not self._cache:
                logger.debug("Cache empty, nothing to persist")
                return
            
            # Convert cache to DataFrame
            cache_list = list(self._cache.values())
            df = pd.DataFrame(cache_list)
            
            # Save to ADLS
            self._save_parquet_to_adls(df, self.FP_CACHE_PATH)
            
            logger.debug(f"Persisted cache: {len(cache_list)} entries")
            
        except Exception as e:
            logger.error(f"Error persisting cache: {e}")
    
    def populate_from_historical_data(self) -> int:
        """
        ONE-TIME migration: Calculate performance for all properties from historical data.
        Returns number of properties processed.
        """
        try:
            from app.core.iceberg import read_table, table_exists
            
            logger.info("[FP-CACHE] Starting historical data population...")
            
            if not table_exists(NAMESPACE, "properties"):
                logger.warning("Properties table does not exist")
                return 0
            
            properties_df = read_table(NAMESPACE, "properties")
            processed = 0
            
            for _, property_row in properties_df.iterrows():
                property_id = UUID(property_row['id'])
                user_id = UUID(property_row['user_id'])
                
                logger.info(f"[FP-CACHE] Processing property {property_id}")
                
                # Calculate for property-level
                self._recalculate_and_persist(property_id, user_id, None)
                processed += 1
                
                # TODO: If multi-unit, also calculate for each unit
                # Would need to query units table
            
            logger.info(f"[FP-CACHE] Historical population complete: {processed} properties")
            return processed
            
        except Exception as e:
            logger.error(f"Error populating historical data: {e}", exc_info=True)
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "initialized": self._initialized,
            "entries_count": len(self._cache),
            "cache_loaded_at": self._cache_loaded_at.isoformat() if self._cache_loaded_at else None,
        }


# Global singleton
financial_performance_cache = FinancialPerformanceCacheService()

