"""FastAPI dependencies"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedError

security = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Dependency to get current user ID from JWT token.
    Raises UnauthorizedError if token is invalid or missing.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise UnauthorizedError("Invalid authentication credentials")
    
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Invalid token payload")
    
    return user_id


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get current user from JWT token.
    Returns the full token payload as a dict.
    Raises UnauthorizedError if token is invalid or missing.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise UnauthorizedError("Invalid authentication credentials")
    
    return payload

