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
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Database / Iceberg
    ICEBERG_CATALOG_TYPE: str = "hadoop"  # Options: "hadoop", "jdbc", "rest" (nessie), "hive"
    ICEBERG_CATALOG_URI: str = ""  # For REST catalog (Nessie)
    DATABASE_URL: str = ""  # For JDBC catalog or warehouse path for HadoopCatalog
    # HadoopCatalog warehouse path format: abfss://container@storageaccount.dfs.core.windows.net/path
    # Or use Azure Blob Storage: wasbs://container@storageaccount.blob.core.windows.net/path
    
    # Azure Storage
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER_NAME: str = "documents"
    
    # Azure Key Vault
    AZURE_KEY_VAULT_NAME: str = "investflow-kv"
    
    # Application Insights
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings()

