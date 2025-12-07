"""FastAPI application entry point"""
import warnings
# Suppress PyIceberg Avro decoder warning before any imports
warnings.filterwarnings("ignore", message="Falling back to pure Python Avro decoder")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.middleware import (
    exception_handler,
    http_exception_handler,
    validation_exception_handler
)
from app.core.exceptions import InvestFlowException
from app.api import auth, health, properties, users, units, scheduled, shares, rent, expenses, documents, financial_performance, scheduled_template
# Temporarily disabled
# from app.api import lakekeeper_test
from app.models.base import Base

# Set up logging
setup_logging()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Rental Property Management API",
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    swagger_ui_parameters={
        "persistAuthorization": True,  # Keep auth token after page refresh
    }
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list if settings.cors_origins_list != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Exception handlers
app.add_exception_handler(InvestFlowException, exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, exception_handler)

# Mount static files for Swagger UI customization
try:
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
except Exception:
    pass  # Ignore if static directory doesn't exist

# Mount static files for Swagger UI customization
try:
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
except Exception:
    pass  # Ignore if static directory doesn't exist


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "api_prefix": settings.API_V1_PREFIX
    }


# Create database tables on startup (in production, use migrations instead)
@app.on_event("startup")
async def startup_event():
    """Initialize database, Iceberg, and auth cache on startup"""
    try:
        from app.core.database import get_engine
        engine = get_engine()
        # In production, use Alembic migrations instead of create_all
        if settings.ENVIRONMENT == "development":
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning(f"Could not initialize database: {e}")

    try:
        from app.core.iceberg import get_catalog
        get_catalog()  # Initialize catalog
        logger.info("PyIceberg catalog initialized")
    except Exception as e:
        logger.warning(f"Could not initialize PyIceberg catalog: {e}")
    
    # Initialize auth cache (CDC parquet cache for fast authentication and sharing)
    try:
        from app.services.auth_cache_service import auth_cache
        if auth_cache.initialize():
            stats = auth_cache.get_stats()
            logger.info(f"Auth cache initialized: {stats['users_count']} users, {stats['shares_count']} shares")
        else:
            logger.warning("Auth cache initialization failed, will use Iceberg fallback on first request")
    except Exception as e:
        logger.warning(f"Could not initialize auth cache: {e}")


# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(properties.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(units.router, prefix=settings.API_V1_PREFIX)
app.include_router(scheduled.router, prefix=settings.API_V1_PREFIX)
app.include_router(scheduled_template.router, prefix=settings.API_V1_PREFIX)
app.include_router(shares.router, prefix=settings.API_V1_PREFIX)
app.include_router(rent.router, prefix=settings.API_V1_PREFIX)
app.include_router(expenses.router, prefix=settings.API_V1_PREFIX)
app.include_router(documents.router, prefix=settings.API_V1_PREFIX)
app.include_router(financial_performance.router, prefix=settings.API_V1_PREFIX)
# Temporarily disabled
# app.include_router(lakekeeper_test.router, prefix=settings.API_V1_PREFIX)

