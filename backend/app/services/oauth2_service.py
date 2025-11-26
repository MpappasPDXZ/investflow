"""
OAuth2 Service for obtaining access tokens from Azure AD
Used for authenticating backend requests to Lakekeeper
"""
import httpx
import logging
from typing import Optional
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


class OAuth2Service:
    """
    Service for managing OAuth2 client credentials flow with Azure AD.
    Handles token acquisition and automatic refresh.
    """
    
    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._authority: str = ""
        self._token_endpoint: str = ""
        self._initialized = False
    
    def _initialize(self):
        """Initialize OAuth2 configuration"""
        if self._initialized:
            return
        
        # Construct authority URL from tenant ID
        if settings.LAKEKEEPER__OAUTH2__AUTHORITY:
            self._authority = settings.LAKEKEEPER__OAUTH2__AUTHORITY
        elif settings.LAKEKEEPER__OAUTH2__TENANT_ID:
            self._authority = f"https://login.microsoftonline.com/{settings.LAKEKEEPER__OAUTH2__TENANT_ID}"
        else:
            logger.warning("OAuth2 not configured - no tenant ID or authority provided")
            self._initialized = True
            return
        
        # Token endpoint for client credentials flow
        self._token_endpoint = f"{self._authority}/oauth2/v2.0/token"
        self._initialized = True
        logger.info(f"OAuth2 service initialized with authority: {self._authority}")
    
    async def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.
        
        Args:
            force_refresh: Force token refresh even if current token is valid
            
        Returns:
            Access token string, or None if OAuth2 is not configured
        """
        self._initialize()
        
        # Check if OAuth2 is configured
        if not settings.LAKEKEEPER__OAUTH2__CLIENT_ID or not settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET:
            logger.debug("OAuth2 not configured - returning None")
            return None
        
        # Check if we have a valid token
        if not force_refresh and self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):  # Refresh 5 min before expiry
                return self._access_token
        
        # Acquire new token
        try:
            token_data = await self._acquire_token()
            if token_data:
                self._access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                logger.info("Successfully acquired OAuth2 access token")
                return self._access_token
        except Exception as e:
            logger.error(f"Failed to acquire OAuth2 token: {e}", exc_info=True)
            # Return cached token if available, even if expired
            return self._access_token
        
        return None
    
    async def _acquire_token(self) -> Optional[dict]:
        """
        Acquire access token using client credentials flow.
        
        Returns:
            Token response dict with access_token and expires_in
        """
        if not self._token_endpoint:
            return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._token_endpoint,
                    data={
                        "client_id": settings.LAKEKEEPER__OAUTH2__CLIENT_ID,
                        "client_secret": settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET,
                        "scope": settings.LAKEKEEPER__OAUTH2__SCOPE,
                        "grant_type": "client_credentials"
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"HTTP error acquiring token: {e}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error acquiring token: {e}")
                raise
    
    def get_oauth2_config(self) -> Optional[dict]:
        """
        Get OAuth2 configuration for REST catalog clients (PyIceberg, DuckDB, etc.).
        
        Returns:
            Dict with client_id, client_secret, scope, and server_uri, or None if not configured
        """
        self._initialize()
        
        if not settings.LAKEKEEPER__OAUTH2__CLIENT_ID or not settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET:
            return None
        
        return {
            "client_id": settings.LAKEKEEPER__OAUTH2__CLIENT_ID,
            "client_secret": settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET,
            "scope": settings.LAKEKEEPER__OAUTH2__SCOPE,
            "server_uri": self._token_endpoint if self._token_endpoint else ""
        }


# Global instance
oauth2_service = OAuth2Service()


def get_oauth2_service() -> OAuth2Service:
    """Dependency for FastAPI routes"""
    return oauth2_service

