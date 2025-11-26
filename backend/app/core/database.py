"""Database connection and SQLAlchemy setup"""
from typing import Optional
from urllib.parse import quote_plus
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global engine instances
engine: Optional[Engine] = None
async_engine: Optional[AsyncEngine] = None
SessionLocal: Optional[sessionmaker] = None
AsyncSessionLocal: Optional[async_sessionmaker] = None


def build_database_url() -> str:
    """
    Build PostgreSQL connection URL from settings.
    URL-encodes password to handle special characters.
    """
    if not all([settings.POSTGRES_HOST, settings.POSTGRES_DB, settings.POSTGRES_USER, settings.POSTGRES_PASSWORD]):
        raise ValueError(
            "PostgreSQL configuration incomplete. Please set POSTGRES_HOST, POSTGRES_DB, "
            "POSTGRES_USER, and POSTGRES_PASSWORD environment variables."
        )
    
    # URL-encode password to handle special characters
    encoded_password = quote_plus(settings.POSTGRES_PASSWORD)
    encoded_user = quote_plus(settings.POSTGRES_USER)
    
    database_url = (
        f"postgresql://{encoded_user}:{encoded_password}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    
    return database_url


def build_async_database_url() -> str:
    """
    Build async PostgreSQL connection URL from settings.
    Uses asyncpg driver for async operations.
    """
    if not all([settings.POSTGRES_HOST, settings.POSTGRES_DB, settings.POSTGRES_USER, settings.POSTGRES_PASSWORD]):
        raise ValueError(
            "PostgreSQL configuration incomplete. Please set POSTGRES_HOST, POSTGRES_DB, "
            "POSTGRES_USER, and POSTGRES_PASSWORD environment variables."
        )
    
    # URL-encode password to handle special characters
    encoded_password = quote_plus(settings.POSTGRES_PASSWORD)
    encoded_user = quote_plus(settings.POSTGRES_USER)
    
    database_url = (
        f"postgresql+asyncpg://{encoded_user}:{encoded_password}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    
    return database_url


def get_engine() -> Engine:
    """
    Get or create the SQLAlchemy synchronous engine.
    Uses PostgreSQL connection configured via environment variables.
    """
    global engine
    
    if engine is None:
        database_url = build_database_url()
        engine = create_engine(
            database_url,
            echo=settings.DEBUG,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10
        )
        logger.info(f"PostgreSQL database engine created for {settings.POSTGRES_HOST}")
    
    return engine


def get_async_engine() -> AsyncEngine:
    """
    Get or create the SQLAlchemy async engine.
    Uses PostgreSQL with asyncpg driver configured via environment variables.
    """
    global async_engine
    
    if async_engine is None:
        database_url = build_async_database_url()
        async_engine = create_async_engine(
            database_url,
            echo=settings.DEBUG,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10
        )
        logger.info(f"PostgreSQL async database engine created for {settings.POSTGRES_HOST}")
    
    return async_engine


def get_session() -> sessionmaker:
    """Get database session factory"""
    global SessionLocal
    
    if SessionLocal is None:
        engine = get_engine()
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
    
    return SessionLocal


def get_async_session() -> async_sessionmaker:
    """Get async database session factory"""
    global AsyncSessionLocal
    
    if AsyncSessionLocal is None:
        async_engine = get_async_engine()
        AsyncSessionLocal = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    return AsyncSessionLocal


def get_db() -> Session:
    """
    Dependency for FastAPI to get database session.
    Use in route handlers: db: Session = Depends(get_db)
    """
    SessionLocal = get_session()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncSession:
    """
    Dependency for FastAPI to get async database session.
    Use in async route handlers: db: AsyncSession = Depends(get_async_db)
    """
    AsyncSessionLocal = get_async_session()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def close_connections() -> None:
    """Close all database connections"""
    global engine, async_engine
    
    if async_engine:
        # Note: async engine cleanup should be done properly
        logger.info("Closing async database connections")
    
    if engine:
        engine.dispose()
        logger.info("Closed database connections")
