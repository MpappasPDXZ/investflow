"""Application configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pydantic import field_validator


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
    AZURE_STORAGE_ACCOUNT_NAME: str = "investflowadls"
    AZURE_STORAGE_ACCOUNT_KEY: str = ""
    AZURE_STORAGE_CONTAINER_NAME: str = "documents"
    
    # Azure Key Vault
    AZURE_KEY_VAULT_NAME: str = "investflow-kv"
    
    # Application Insights
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""
    
    # Lakekeeper Configuration (optional - for data lake management)
    LAKEKEEPER__BASE_URI: str = "http://localhost:8181"
    LAKEKEEPER__PG_DATABASE_URL_READ: str = ""
    LAKEKEEPER__PG_DATABASE_URL_WRITE: str = ""
    LAKEKEEPER__PG_ENCRYPTION_KEY: str = ""
    LAKEKEEPER__ENABLE_AZURE_SYSTEM_CREDENTIALS: bool = False
    # Optional: OAuth2 token for Lakekeeper authentication (if using external auth)
    LAKEKEEPER__AUTH_TOKEN: str = ""
    # Default warehouse name to use
    LAKEKEEPER__WAREHOUSE_NAME: str = "lakekeeper"
    
    # OAuth2 Configuration for Lakekeeper (Azure AD)
    LAKEKEEPER__OAUTH2__CLIENT_ID: str = ""
    LAKEKEEPER__OAUTH2__CLIENT_SECRET: str = ""
    LAKEKEEPER__OAUTH2__TENANT_ID: str = ""
    LAKEKEEPER__OAUTH2__SCOPE: str = "api://lakekeeper/.default"
    LAKEKEEPER__OAUTH2__AUTHORITY: str = ""  # Auto-constructed from tenant_id if not set
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    


# Global settings instance
settings = Settings()

