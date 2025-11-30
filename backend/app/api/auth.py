"""Authentication endpoints"""
from datetime import timedelta
from typing import Optional
import uuid
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password
)
from app.core.dependencies import security
from app.core.exceptions import UnauthorizedError, ConflictError
from app.schemas.auth import UserRegister, UserLogin, Token
from app.core.iceberg import read_table, append_data, table_exists
from app.core.logging import get_logger

NAMESPACE = ("investflow",)
TABLE_NAME = "users"

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = get_logger(__name__)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
):
    """Register a new user in Iceberg"""
    try:
        # Check if user already exists
        if table_exists(NAMESPACE, TABLE_NAME):
            df = read_table(NAMESPACE, TABLE_NAME)
            existing = df[df["email"] == user_data.email]
            if len(existing) > 0:
                logger.warning(f"Registration failed - user already exists: {user_data.email}")
                raise ConflictError("User with this email already exists")
        
        # Create user with string UUID
        user_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        # Create user record
        user_dict = {
            "id": user_id,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "email": user_data.email,
            "password_hash": get_password_hash(user_data.password),
            "tax_rate": float(user_data.tax_rate) if user_data.tax_rate is not None else None,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
        }
        
        # Append to Iceberg table
        df = pd.DataFrame([user_dict])
        append_data(NAMESPACE, TABLE_NAME, df)
        
        # Generate access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_id, "email": user_data.email},
            expires_delta=access_token_expires
        )
        
        return Token(access_token=access_token)
        
    except ConflictError:
        raise
    except Exception as e:
        logger.error(f"Error registering user {user_data.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register user: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
):
    """Login and get access token from Iceberg"""
    try:
        logger.info(f"Login attempt for email: {credentials.email}")
        
        # Get user from Iceberg
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error("Users table does not exist")
            raise UnauthorizedError("Incorrect email or password")
        
        df = read_table(NAMESPACE, TABLE_NAME)
        logger.info(f"Read {len(df)} users from table")
        logger.info(f"Columns in users table: {df.columns.tolist()}")
        logger.info(f"Emails in table: {df['email'].tolist()}")
        
        user_rows = df[df["email"] == credentials.email]
        
        if len(user_rows) == 0:
            logger.warning(f"No user found with email: {credentials.email}")
            raise UnauthorizedError("Incorrect email or password")
        
        user = user_rows.iloc[0]
        logger.info(f"Found user: {user['id']}")
        logger.info(f"User has password_hash: {'password_hash' in user and pd.notna(user.get('password_hash'))}")
        
        # Verify password
        password_hash = user.get("password_hash")
        if not password_hash or pd.isna(password_hash):
            logger.error("User has no password_hash")
            raise UnauthorizedError("Incorrect email or password")
            
        if not verify_password(credentials.password, password_hash):
            logger.warning("Password verification failed")
            raise UnauthorizedError("Incorrect email or password")
        
        # Check if user is active
        is_active = user.get("is_active", True)
        if pd.notna(is_active) and not bool(is_active):
            logger.warning("User account is inactive")
            raise UnauthorizedError("User account is inactive")
        
        user_id = str(user["id"])
        user_email = user["email"]
        
        logger.info(f"Login successful for user: {user_id}")
        
        # Generate access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_id, "email": user_email},
            expires_delta=access_token_expires
        )
        
        return Token(access_token=access_token)
    except UnauthorizedError:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise UnauthorizedError("Incorrect email or password")


@router.post("/refresh", response_model=Token)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Refresh access token.
    TODO: Implement token refresh logic
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise UnauthorizedError("Invalid token")
    
    user_id = payload.get("sub")
    email = payload.get("email")
    
    if not user_id or not email:
        raise UnauthorizedError("Invalid token payload")
    
    # Create new token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id, "email": email},
        expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token)

