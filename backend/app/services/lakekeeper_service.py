"""
Lakekeeper Service - Handles communication with Lakekeeper REST API
Provides authorization and credential management for DuckDB queries
"""
import httpx
import logging
from typing import Optional, Dict, Any
from app.core.config import settings
from app.services.oauth2_service import oauth2_service

logger = logging.getLogger(__name__)


class LakekeeperService:
    """Service for interacting with Lakekeeper REST catalog and management APIs"""
    
    def __init__(self):
        self.base_uri = settings.LAKEKEEPER__BASE_URI
        self.catalog_uri = f"{self.base_uri}/catalog"
        self.management_uri = f"{self.base_uri}/management"
        self.auth_token: Optional[str] = settings.LAKEKEEPER__AUTH_TOKEN or None  # Static token if provided
        self.warehouse_name: str = settings.LAKEKEEPER__WAREHOUSE_NAME
        self._use_oauth2: bool = bool(
            settings.LAKEKEEPER__OAUTH2__CLIENT_ID and 
            settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET
        )
        
    async def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Lakekeeper API requests with authentication"""
        headers = {"Content-Type": "application/json"}
        
        # Get authentication token (OAuth2 or static)
        token = None
        if self._use_oauth2:
            # Use OAuth2 service to get token
            token = await oauth2_service.get_access_token()
        elif self.auth_token:
            # Use static token if provided
            token = self.auth_token
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        return headers
    
    async def get_warehouses(self) -> list:
        """Get list of warehouses from Lakekeeper"""
        async with httpx.AsyncClient() as client:
            try:
                headers = await self._get_headers()
                response = await client.get(
                    f"{self.management_uri}/v1/warehouse",
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("warehouses", [])
            except httpx.HTTPError as e:
                logger.error(f"Failed to get warehouses from Lakekeeper: {e}")
                raise
    
    async def get_warehouse_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get warehouse by name"""
        warehouses = await self.get_warehouses()
        for warehouse in warehouses:
            if warehouse.get("name") == name:
                return warehouse
        return None
    
    async def get_warehouse_id(self, name: str = "lakekeeper") -> Optional[str]:
        """Get warehouse UUID by name"""
        warehouse = await self.get_warehouse_by_name(name)
        return warehouse.get("id") if warehouse else None
    
    async def create_namespace(self, warehouse_id: str, namespace: list[str]) -> Dict[str, Any]:
        """Create a namespace in Lakekeeper"""
        async with httpx.AsyncClient() as client:
            try:
                headers = await self._get_headers()
                response = await client.post(
                    f"{self.catalog_uri}/v1/{warehouse_id}/namespaces",
                    json={"namespace": namespace},
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to create namespace: {e}")
                raise
    
    async def list_namespaces(self, warehouse_id: str) -> list:
        """List namespaces in a warehouse"""
        async with httpx.AsyncClient() as client:
            try:
                headers = await self._get_headers()
                response = await client.get(
                    f"{self.catalog_uri}/v1/{warehouse_id}/namespaces",
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("namespaces", [])
            except httpx.HTTPError as e:
                logger.error(f"Failed to list namespaces: {e}")
                raise
    
    async def create_table(
        self, 
        warehouse_id: str, 
        namespace: list[str], 
        table_name: str,
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an Iceberg table in Lakekeeper"""
        async with httpx.AsyncClient() as client:
            try:
                headers = await self._get_headers()
                namespace_path = "/".join(namespace)
                response = await client.post(
                    f"{self.catalog_uri}/v1/{warehouse_id}/namespaces/{namespace_path}/tables",
                    json={
                        "name": table_name,
                        "schema": schema
                    },
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to create table: {e}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                raise
    
    async def get_table(
        self,
        warehouse_id: str,
        namespace: list[str],
        table_name: str
    ) -> Dict[str, Any]:
        """Get table metadata including vended credentials for DuckDB"""
        async with httpx.AsyncClient() as client:
            try:
                headers = await self._get_headers()
                namespace_path = "/".join(namespace)
                response = await client.get(
                    f"{self.catalog_uri}/v1/{warehouse_id}/namespaces/{namespace_path}/tables/{table_name}",
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to get table: {e}")
                raise
    
    async def get_table_config(
        self,
        warehouse_id: str,
        namespace: list[str],
        table_name: str
    ) -> Dict[str, Any]:
        """Get table configuration including storage credentials (vended by Lakekeeper)"""
        table_info = await self.get_table(warehouse_id, namespace, table_name)
        
        # Extract vended credentials from Lakekeeper response
        # Lakekeeper returns storage-credentials with SAS tokens for Azure ADLS
        config = table_info.get("config", {})
        storage_credentials = table_info.get("storage-credentials", [])
        
        return {
            "metadata_location": table_info.get("metadata-location"),
            "config": config,
            "storage_credentials": storage_credentials,
            "table_metadata": table_info.get("metadata", {})
        }


# Global instance
lakekeeper_service = LakekeeperService()


def get_lakekeeper_service() -> LakekeeperService:
    """Dependency for FastAPI routes"""
    return lakekeeper_service

