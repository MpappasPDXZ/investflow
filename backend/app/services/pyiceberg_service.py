"""
PyIceberg service for reading and writing Iceberg tables via Lakekeeper REST catalog.
PyIceberg supports both reads and writes to Azure ADLS Gen2.
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.table import Table
from app.core.config import settings
from app.services.oauth2_service import oauth2_service

logger = logging.getLogger(__name__)


class PyIcebergService:
    """
    Service for interacting with Iceberg tables using PyIceberg.
    Supports both reads and writes to Azure ADLS Gen2 via Lakekeeper REST catalog.
    """
    
    def __init__(self):
        self._catalog: Optional[RestCatalog] = None
        self._warehouse_name: str = settings.LAKEKEEPER__WAREHOUSE_NAME
    
    def get_catalog(self) -> RestCatalog:
        """
        Get or create PyIceberg REST catalog configured with OAuth2.
        
        Returns:
            RestCatalog instance configured for Lakekeeper
        """
        if self._catalog is None:
            self._catalog = self._create_catalog()
        return self._catalog
    
    def _create_catalog(self) -> RestCatalog:
        """Create PyIceberg REST catalog with OAuth2 authentication"""
        catalog_uri = f"{settings.LAKEKEEPER__BASE_URI}/catalog"
        
        # Get OAuth2 configuration
        oauth2_config = oauth2_service.get_oauth2_config()
        
        if not oauth2_config or not oauth2_config.get('client_id') or not oauth2_config.get('client_secret'):
            raise ValueError("OAuth2 configuration required for PyIceberg catalog")
        
        client_id = oauth2_config['client_id']
        client_secret = oauth2_config['client_secret']
        scope = oauth2_config.get('scope', 'api://lakekeeper/.default')
        server_uri = oauth2_config.get('server_uri', '')
        
        # PyIceberg uses credential format: "client_id:client_secret"
        credential = f"{client_id}:{client_secret}"
        
        # Create catalog with OAuth2
        catalog = RestCatalog(
            name="lakekeeper",
            uri=catalog_uri,
            warehouse=self._warehouse_name,
            credential=credential,
            scope=scope,
            **{
                "oauth2-server-uri": server_uri
            }
        )
        
        logger.info(f"Created PyIceberg REST catalog for warehouse '{self._warehouse_name}'")
        return catalog
    
    def load_table(self, namespace: tuple, table_name: str) -> Table:
        """
        Load an Iceberg table from Lakekeeper.
        
        Args:
            namespace: Tuple of namespace parts, e.g., ("test_namespace",)
            table_name: Name of the table
            
        Returns:
            PyIceberg Table object
        """
        catalog = self.get_catalog()
        table_identifier = (*namespace, table_name)
        return catalog.load_table(table_identifier)
    
    def append_data(
        self,
        namespace: tuple,
        table_name: str,
        data: pd.DataFrame
    ) -> None:
        """
        Append data to an Iceberg table using PyIceberg.
        
        Args:
            namespace: Tuple of namespace parts, e.g., ("test_namespace",)
            table_name: Name of the table
            data: Pandas DataFrame to append
        """
        table = self.load_table(namespace, table_name)
        
        # Get table schema to ensure data types match
        table_schema = table.schema()
        data_copy = data.copy()
        
        # Convert data types to match table schema
        for field in table_schema.fields:
            col_name = field.name
            if col_name in data_copy.columns:
                field_type = str(field.field_type)
                
                # Handle timestamp precision (convert ns to us)
                if pd.api.types.is_datetime64_any_dtype(data_copy[col_name]):
                    data_copy[col_name] = data_copy[col_name].astype('datetime64[us]')
                # Handle integer types (ensure int32 for int fields)
                elif 'int' in field_type.lower() and 'long' not in field_type.lower():
                    # Convert to int32 if table expects int
                    if data_copy[col_name].dtype in ['int64', 'Int64']:
                        data_copy[col_name] = data_copy[col_name].astype('int32')
        
        # Convert DataFrame to PyArrow Table
        arrow_table = pa.Table.from_pandas(data_copy)
        
        # Ensure schema matches table schema (required fields must be non-nullable)
        table_schema_pa = table.schema().as_arrow()
        # Convert arrow_table to match table schema
        # PyIceberg will handle the conversion, but we need to ensure types match
        # The append method should handle this, but let's ensure nullable matches
        converted_arrays = []
        converted_fields = []
        for i, field in enumerate(table_schema_pa):
            if i < len(arrow_table.schema):
                arrow_field = arrow_table.schema[i]
                arrow_array = arrow_table.column(i)
                
                # Cast to match table field type if needed
                if arrow_field.type != field.type:
                    arrow_array = arrow_array.cast(field.type)
                
                # Use table field (with correct nullable setting)
                converted_fields.append(field)
                converted_arrays.append(arrow_array)
            else:
                # Missing field - this shouldn't happen
                converted_fields.append(field)
                converted_arrays.append(pa.nulls(len(data_copy), type=field.type))
        
        arrow_table = pa.Table.from_arrays(converted_arrays, schema=pa.schema(converted_fields))
        
        # Append data to table
        table.append(arrow_table)
        
        logger.info(f"Appended {len(data)} rows to {'.'.join((*namespace, table_name))}")
    
    def create_table(
        self,
        namespace: tuple,
        table_name: str,
        schema: pa.Schema,
        properties: Optional[Dict[str, str]] = None
    ) -> Table:
        """
        Create a new Iceberg table via PyIceberg.
        
        Args:
            namespace: Tuple of namespace parts, e.g., ("test_namespace",)
            table_name: Name of the table
            schema: PyArrow schema for the table
            properties: Optional table properties
            
        Returns:
            Created PyIceberg Table object
        """
        catalog = self.get_catalog()
        table_identifier = (*namespace, table_name)
        
        # Create table
        table = catalog.create_table(
            identifier=table_identifier,
            schema=schema,
            properties=properties or {}
        )
        
        logger.info(f"Created table {'.'.join(table_identifier)}")
        return table
    
    def read_table(
        self,
        namespace: tuple,
        table_name: str,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Read data from an Iceberg table using PyIceberg.
        
        Args:
            namespace: Tuple of namespace parts, e.g., ("test_namespace",)
            table_name: Name of the table
            limit: Optional limit on number of rows to return
            
        Returns:
            Pandas DataFrame with table data
        """
        table = self.load_table(namespace, table_name)
        
        # Scan table and convert to Pandas
        scan = table.scan()
        if limit:
            scan = scan.limit(limit)
        
        arrow_table = scan.to_arrow()
        df = arrow_table.to_pandas()
        
        logger.info(f"Read {len(df)} rows from {'.'.join((*namespace, table_name))}")
        return df
    
    def query_table(
        self,
        namespace: tuple,
        table_name: str,
        filter_expr: Optional[str] = None,
        select_columns: Optional[list] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Query an Iceberg table with optional filtering and column selection.
        
        Args:
            namespace: Tuple of namespace parts, e.g., ("test_namespace",)
            table_name: Name of the table
            filter_expr: Optional filter expression (e.g., "id > 5")
            select_columns: Optional list of column names to select
            limit: Optional limit on number of rows to return
            
        Returns:
            Pandas DataFrame with query results
        """
        table = self.load_table(namespace, table_name)
        
        # Build scan with filters
        scan = table.scan()
        
        # Note: PyIceberg filtering requires using PyIceberg expressions
        # For simple cases, we can scan and filter in Pandas
        # For complex filters, use PyIceberg's expression API
        
        arrow_table = scan.to_arrow()
        df = arrow_table.to_pandas()
        
        # Apply filter if provided (simple string-based filtering)
        if filter_expr:
            # This is a simple approach - for complex filters, use PyIceberg expressions
            df = df.query(filter_expr)
        
        # Select columns if specified
        if select_columns:
            df = df[select_columns]
        
        # Apply limit
        if limit:
            df = df.head(limit)
        
        logger.info(f"Queried {len(df)} rows from {'.'.join((*namespace, table_name))}")
        return df
    
    def drop_table(
        self,
        namespace: tuple,
        table_name: str
    ) -> None:
        """
        Drop an Iceberg table.
        
        Args:
            namespace: Tuple of namespace parts, e.g., ("investflow",)
            table_name: Name of the table
        """
        catalog = self.get_catalog()
        table_identifier = (*namespace, table_name)
        
        try:
            catalog.drop_table(table_identifier)
            logger.info(f"Dropped table {'.'.join(table_identifier)}")
        except Exception as e:
            # Table might not exist, which is fine
            if "does not exist" in str(e).lower() or "not found" in str(e).lower():
                logger.debug(f"Table {'.'.join(table_identifier)} does not exist (skipping drop)")
            else:
                raise
    
    def table_exists(
        self,
        namespace: tuple,
        table_name: str
    ) -> bool:
        """
        Check if a table exists.
        
        Args:
            namespace: Tuple of namespace parts, e.g., ("investflow",)
            table_name: Name of the table
            
        Returns:
            True if table exists, False otherwise
        """
        catalog = self.get_catalog()
        table_identifier = (*namespace, table_name)
        
        try:
            catalog.load_table(table_identifier)
            return True
        except Exception:
            return False
    
    def truncate_table(
        self,
        namespace: tuple,
        table_name: str,
        schema: pa.Schema,
        properties: Optional[Dict[str, str]] = None
    ) -> Table:
        """
        Truncate a table by dropping and recreating it.
        
        Args:
            namespace: Tuple of namespace parts, e.g., ("investflow",)
            table_name: Name of the table
            schema: PyArrow schema for the table
            properties: Optional table properties
            
        Returns:
            Created PyIceberg Table object
        """
        # Drop table if it exists
        self.drop_table(namespace, table_name)
        
        # Recreate table
        return self.create_table(namespace, table_name, schema, properties)


# Global instance
pyiceberg_service = PyIcebergService()


def get_pyiceberg_service() -> PyIcebergService:
    """Get PyIceberg service instance"""
    return pyiceberg_service

