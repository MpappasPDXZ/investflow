"""Logging configuration"""
import logging
import sys
from typing import Any

from opencensus.ext.azure.log_exporter import AzureLogHandler
from app.core.config import settings


def setup_logging() -> None:
    """Configure application logging"""
    # Suppress PyIceberg Avro decoder warning first
    import warnings
    warnings.filterwarnings("ignore", message="Falling back to pure Python Avro decoder")
    
    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Suppress verbose Azure SDK logging
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("azure.storage").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Azure Application Insights handler (if configured)
    if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
        try:
            azure_handler = AzureLogHandler(
                connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING
            )
            azure_handler.setLevel(logging.WARNING)  # Only send warnings and errors
            logger.addHandler(azure_handler)
        except Exception as e:
            logger.warning(f"Failed to set up Azure Log Handler: {e}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)

