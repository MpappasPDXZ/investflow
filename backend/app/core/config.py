"""Application configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "InvestFlow API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for development
    
    # CORS - stored as string, parsed to list via property
    CORS_ORIGINS: str = "http://localhost:3000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list (parsed from comma-separated string)"""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return origins if origins else ["http://localhost:3000"]
    
    
    # Azure PostgreSQL Configuration
    POSTGRES_HOST: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = ""
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    
    # Azure ADLS Gen2 Configuration
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_ACCOUNT_NAME: str = ""  # Extracted from connection string if not set
    AZURE_STORAGE_ACCOUNT_KEY: str = ""   # Extracted from connection string if not set
    AZURE_STORAGE_CONTAINER_NAME: str = "documents"
    
    # CDC Cache Configuration (defaults to documents container if not set)
    CDC_CACHE_CONTAINER_NAME: str = ""  # Leave empty to use AZURE_STORAGE_CONTAINER_NAME
    
    # Azure Key Vault
    AZURE_KEY_VAULT_NAME: str = "investflow-kv"
    
    # Application Insights
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""

    # When true, all tabular reads/writes use Postgres (always on after Lakekeeper teardown).
    USE_POSTGRES_STORE: bool = True
    # Inventory of tables in app schema (kept for scripts / ops).
    POSTGRES_MIGRATED_TABLES: str = "scheduled_expenses,scheduled_revenue,units,tenants,rents,leases,walkthroughs,walkthrough_areas,properties,users,user_shares,vault,expenses,comps,tenant_landlord_references"

    # Legacy Lakekeeper env vars (ignored at runtime; accepted so old Container App env does not crash Settings)
    LAKEKEEPER__BASE_URI: str = ""
    LAKEKEEPER__PG_DATABASE_URL_READ: str = ""
    LAKEKEEPER__PG_DATABASE_URL_WRITE: str = ""
    LAKEKEEPER__PG_ENCRYPTION_KEY: str = ""
    LAKEKEEPER__ENABLE_AZURE_SYSTEM_CREDENTIALS: bool = False
    LAKEKEEPER__AUTH_TOKEN: str = ""
    LAKEKEEPER__WAREHOUSE_NAME: str = ""
    LAKEKEEPER__OAUTH2__CLIENT_ID: str = ""
    LAKEKEEPER__OAUTH2__CLIENT_SECRET: str = ""
    LAKEKEEPER__OAUTH2__TENANT_ID: str = ""
    LAKEKEEPER__OAUTH2__SCOPE: str = ""
    LAKEKEEPER__OAUTH2__AUTHORITY: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
