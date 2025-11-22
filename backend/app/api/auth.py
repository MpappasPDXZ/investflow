"""Authentication endpoints"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    decode_access_token
)
from app.core.dependencies import security
from app.core.exceptions import UnauthorizedError, ConflictError
from app.schemas.auth import UserRegister, UserLogin, Token

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """
    Register a new user.
    TODO: Implement actual user creation in database
    """
    # TODO: Check if user already exists in database
    # TODO: Create user in database
    # For now, return a mock response
    
    # Mock: Check if user exists (will be replaced with database query)
    # if await user_exists(user_data.email):
    #     raise ConflictError("User with this email already exists")
    
    # Mock: Create user (will be replaced with database insert)
    # user_id = await create_user(user_data)
    
    # For now, generate a token with mock user_id
    # This will be replaced with actual user creation
    user_id = "mock-user-id"  # TODO: Replace with actual user ID from database
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id, "email": user_data.email},
        expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token)


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """
    Login and get access token.
    TODO: Implement actual user authentication against database
    """
    # TODO: Get user from database by email
    # user = await get_user_by_email(credentials.email)
    # if not user:
    #     raise UnauthorizedError("Incorrect email or password")
    
    # TODO: Verify password
    # if not verify_password(credentials.password, user.hashed_password):
    #     raise UnauthorizedError("Incorrect email or password")
    
    # For now, return a mock response
    # This will be replaced with actual authentication
    user_id = "mock-user-id"  # TODO: Replace with actual user ID from database
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id, "email": credentials.email},
        expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token)


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

