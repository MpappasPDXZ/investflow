"""
Scheduled Financials Template Cache Service

Stores a TEMPLATE property's scheduled expenses/revenue in ADLS parquet.
Allows auto-applying scaled templates to new properties based on:
- Purchase price ratio
- Bedrooms/bathrooms ratio
- Square footage ratio
"""
import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Optional, Dict, List, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from azure.storage.blob import BlobServiceClient
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = ("investflow",)


class ScheduledFinancialsTemplateService:
    """
    Cache for scheduled financials templates.
    Stores a reference property's scheduled expenses/revenue as a template.
    """
    
    # ADLS paths for template cache
    TEMPLATE_EXPENSES_PATH = "cdc/scheduled_financials_template/expenses.parquet"
    TEMPLATE_REVENUE_PATH = "cdc/scheduled_financials_template/revenue.parquet"
    TEMPLATE_METADATA_PATH = "cdc/scheduled_financials_template/metadata.parquet"
    
    @property
    def cache_container(self) -> str:
        """Get the container name for CDC cache"""
        if settings.CDC_CACHE_CONTAINER_NAME:
            return settings.CDC_CACHE_CONTAINER_NAME
        return settings.AZURE_STORAGE_CONTAINER_NAME or "documents"
    
    def __init__(self):
        self._expenses_template: List[Dict[str, Any]] = []
        self._revenue_template: List[Dict[str, Any]] = []
        self._template_metadata: Optional[Dict[str, Any]] = None
        self._initialized = False
        self._blob_service: Optional[BlobServiceClient] = None
    
    def _get_blob_service(self) -> Optional[BlobServiceClient]:
        """Get or create Azure Blob client"""
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
                logger.warning("Azure Storage not configured, template cache disabled")
                return None
            
            return self._blob_service
        except Exception as e:
            logger.error(f"Failed to initialize blob service: {e}")
            return None
    
    def initialize(self) -> bool:
        """Initialize the template cache on startup"""
        if self._initialized:
            return True
        
        logger.info("Initializing scheduled financials template cache...")
        
        if self._load_from_adls():
            logger.info(f"Template loaded: {len(self._expenses_template)} expenses, {len(self._revenue_template)} revenue items")
            self._initialized = True
            return True
        
        logger.info("No template found in ADLS")
        self._initialized = True
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
                return None
            
            stream = io.BytesIO()
            blob_client.download_blob().readinto(stream)
            stream.seek(0)
            
            df = pq.read_table(stream).to_pandas()
            return df
            
        except Exception as e:
            logger.error(f"Error reading parquet from ADLS ({blob_path}): {e}")
            return None
    
    def _save_parquet_to_adls(self, df: pd.DataFrame, blob_path: str) -> bool:
        """Save a DataFrame as parquet to ADLS"""
        blob_service = self._get_blob_service()
        if blob_service is None:
            return False
        
        try:
            container_client = blob_service.get_container_client(self.cache_container)
            if not container_client.exists():
                container_client.create_container()
            
            df = df.copy()
            df["_cdc_timestamp"] = pd.Timestamp.now()
            
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].astype('datetime64[us]')
            
            table = pa.Table.from_pandas(df, preserve_index=False)
            stream = io.BytesIO()
            pq.write_table(table, stream)
            stream.seek(0)
            
            blob_client = blob_service.get_blob_client(
                container=self.cache_container,
                blob=blob_path
            )
            blob_client.upload_blob(stream, overwrite=True)
            
            logger.info(f"Saved template to {blob_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving template to ADLS: {e}")
            return False
    
    def _load_from_adls(self) -> bool:
        """Load template from ADLS"""
        try:
            # Load metadata
            metadata_df = self._read_parquet_from_adls(self.TEMPLATE_METADATA_PATH)
            if metadata_df is not None and not metadata_df.empty:
                self._template_metadata = metadata_df.iloc[0].to_dict()
            
            # Load expenses
            expenses_df = self._read_parquet_from_adls(self.TEMPLATE_EXPENSES_PATH)
            if expenses_df is not None and not expenses_df.empty:
                self._expenses_template = expenses_df.to_dict('records')
            
            # Load revenue
            revenue_df = self._read_parquet_from_adls(self.TEMPLATE_REVENUE_PATH)
            if revenue_df is not None and not revenue_df.empty:
                self._revenue_template = revenue_df.to_dict('records')
            
            return self._template_metadata is not None
            
        except Exception as e:
            logger.error(f"Error loading template: {e}")
            return False
    
    def save_template_from_property(self, property_id: UUID, property_data: Dict[str, Any]) -> bool:
        """
        Save a property's scheduled financials as the template.
        This should be run on 316 S 50th Ave to cache its scheduled expenses.
        """
        try:
            from app.core.iceberg import read_table, table_exists
            
            logger.info(f"Saving template from property {property_id}")
            
            # Get scheduled expenses
            if not table_exists(NAMESPACE, "scheduled_expenses"):
                logger.warning("No scheduled_expenses table")
                return False
            
            expenses_df = read_table(NAMESPACE, "scheduled_expenses")
            expenses_df = expenses_df[expenses_df["property_id"] == str(property_id)]
            
            # Get scheduled revenue
            revenue_df = pd.DataFrame()
            if table_exists(NAMESPACE, "scheduled_revenue"):
                revenue_df = read_table(NAMESPACE, "scheduled_revenue")
                revenue_df = revenue_df[revenue_df["property_id"] == str(property_id)]
            
            # Save metadata (property characteristics for scaling)
            metadata = {
                "template_property_id": str(property_id),
                "purchase_price": property_data.get("purchase_price", 0),
                "bedrooms": property_data.get("bedrooms", 0),
                "bathrooms": property_data.get("bathrooms", 0),
                "square_feet": property_data.get("square_feet", 0),
                "created_at": pd.Timestamp.now()
            }
            metadata_df = pd.DataFrame([metadata])
            
            # Save to ADLS
            self._save_parquet_to_adls(metadata_df, self.TEMPLATE_METADATA_PATH)
            
            if not expenses_df.empty:
                self._save_parquet_to_adls(expenses_df, self.TEMPLATE_EXPENSES_PATH)
            
            if not revenue_df.empty:
                self._save_parquet_to_adls(revenue_df, self.TEMPLATE_REVENUE_PATH)
            
            # Reload cache
            self._load_from_adls()
            
            logger.info(f"✅ Template saved: {len(self._expenses_template)} expenses, {len(self._revenue_template)} revenue")
            return True
            
        except Exception as e:
            logger.error(f"Error saving template: {e}", exc_info=True)
            return False
    
    def apply_template_to_property(
        self,
        target_property_id: UUID,
        target_property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply the template to a new property with intelligent scaling.
        Scales expenses based on purchase price, bedrooms, bathrooms, square feet.
        """
        if not self._initialized:
            self.initialize()
        
        if not self._template_metadata:
            raise ValueError("No template available")
        
        # Calculate scaling factors
        template_price = float(self._template_metadata.get("purchase_price", 1))
        template_beds = float(self._template_metadata.get("bedrooms", 1) or 1)
        template_baths = float(self._template_metadata.get("bathrooms", 1) or 1)
        template_sqft = float(self._template_metadata.get("square_feet", 1) or 1)
        
        target_price = float(target_property_data.get("purchase_price", template_price))
        target_beds = float(target_property_data.get("bedrooms", template_beds) or template_beds)
        target_baths = float(target_property_data.get("bathrooms", template_baths) or template_baths)
        target_sqft = float(target_property_data.get("square_feet", template_sqft) or template_sqft)
        
        price_ratio = target_price / template_price if template_price > 0 else 1
        beds_ratio = target_beds / template_beds if template_beds > 0 else 1
        baths_ratio = target_baths / template_baths if template_baths > 0 else 1
        sqft_ratio = target_sqft / template_sqft if template_sqft > 0 else 1
        
        logger.info(f"Scaling: price={price_ratio:.2f}x, beds={beds_ratio:.2f}x, baths={baths_ratio:.2f}x, sqft={sqft_ratio:.2f}x")
        
        # Helper to clean numeric values (remove NaN, Infinity)
        def clean_value(value):
            if value is None:
                return None
            try:
                val = float(value)
                # Check for NaN or Infinity
                if not (val != val or val == float('inf') or val == float('-inf')):
                    return val
            except (ValueError, TypeError):
                pass
            return None
        
        # Scale expenses
        scaled_expenses = []
        
        # Items that should NOT be scaled (fixed costs)
        NO_SCALE_ITEMS = {
            'Lawn Care (30 mows x 60 per mow)',
            'Sprinklers Turn Off',
            'HVAC',
            'Dryer',
            'Washer',
            'Microwave (Over Range)',
            'Dishwasher',
            'Electric Range',
            'Refrigerator'
        }
        
        # Items that should NOT be added automatically
        EXCLUDE_ITEMS = {
            'Line of Credit',
            'Mortgage'
        }
        
        # Items that scale with square footage
        SQFT_SCALE_ITEMS = {
            'Electricity',
            'Natural Gas',
            'Water',
            'Blinds',
            'Driveway',
            'Doors',
            'Windows',
            'Floors',
            'Floors (Refinishing Hardwoods)',  # Handle variations
            'Insurance'
        }
        
        for exp in self._expenses_template:
            item_name = exp.get("item_name", "")
            
            # Skip excluded items
            if item_name in EXCLUDE_ITEMS:
                continue
            
            scaled = exp.copy()
            scaled["property_id"] = str(target_property_id)
            scaled.pop("id", None)
            scaled.pop("created_at", None)
            scaled.pop("updated_at", None)
            scaled.pop("_cdc_timestamp", None)
            
            exp_type = exp.get("expense_type")
            
            # Don't scale fixed-cost items
            if item_name in NO_SCALE_ITEMS:
                # Keep original values, no scaling
                pass
            
            # Scale with square footage only
            elif item_name in SQFT_SCALE_ITEMS or any(sqft_item in item_name for sqft_item in ['Floor', 'Insurance']):
                if exp_type == "capex" and exp.get("purchase_price"):
                    scaled["purchase_price"] = clean_value(float(exp["purchase_price"]) * sqft_ratio)
                elif exp_type in ["pti", "maintenance", "vacancy"] and exp.get("annual_cost"):
                    # Special handling for Roof - minimum $7000 x 4% per year
                    if 'Roof' in item_name:
                        base_cost = max(7000, float(exp.get("annual_cost", 7000 * 0.04) / 0.04))
                        scaled["purchase_price"] = clean_value(base_cost * sqft_ratio)
                        scaled["depreciation_rate"] = 0.04
                    else:
                        scaled["annual_cost"] = clean_value(float(exp["annual_cost"]) * sqft_ratio)
            
            # Default scaling (price * sqft) for other CapEx
            elif exp_type == "capex" and exp.get("purchase_price"):
                scaled["purchase_price"] = clean_value(float(exp["purchase_price"]) * price_ratio * sqft_ratio)
            
            # PTI and maintenance scale with price and size
            elif exp_type in ["pti", "maintenance"] and exp.get("annual_cost"):
                scaled["annual_cost"] = clean_value(float(exp["annual_cost"]) * price_ratio * sqft_ratio)
            
            # P&I scales with price (loan amount) - but we're excluding these
            elif exp_type == "pi" and exp.get("principal"):
                scaled["principal"] = clean_value(float(exp["principal"]) * price_ratio)
            
            # Clean all numeric fields
            for key, value in scaled.items():
                if isinstance(value, (int, float)) and key not in ['property_id', 'expense_type', 'item_name', 'notes']:
                    scaled[key] = clean_value(value)
            
            scaled_expenses.append(scaled)
        
        # Scale revenue
        scaled_revenue = []
        for rev in self._revenue_template:
            scaled = rev.copy()
            scaled["property_id"] = str(target_property_id)
            scaled.pop("id", None)
            scaled.pop("created_at", None)
            scaled.pop("updated_at", None)
            scaled.pop("_cdc_timestamp", None)
            
            rev_type = rev.get("revenue_type")
            
            if rev_type == "appreciation":
                if rev.get("property_value"):
                    scaled["property_value"] = clean_value(target_price)
            elif rev_type == "principal_paydown":
                if rev.get("annual_amount"):
                    scaled["annual_amount"] = clean_value(float(rev["annual_amount"]) * price_ratio)
            elif rev_type == "value_added":
                if rev.get("value_added_amount"):
                    scaled["value_added_amount"] = clean_value(float(rev["value_added_amount"]) * price_ratio)
            
            # Clean all numeric fields
            for key, value in scaled.items():
                if isinstance(value, (int, float)) and key not in ['property_id', 'revenue_type', 'item_name', 'notes']:
                    scaled[key] = clean_value(value)
            
            scaled_revenue.append(scaled)
        
        return {
            "expenses": scaled_expenses,
            "revenue": scaled_revenue,
            "scaling_factors": {
                "price_ratio": price_ratio,
                "beds_ratio": beds_ratio,
                "baths_ratio": baths_ratio,
                "sqft_ratio": sqft_ratio
            }
        }


# Global singleton
scheduled_financials_template = ScheduledFinancialsTemplateService()




