"""Authentication schemas"""
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    """User registration schema"""
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token data schema"""
    user_id: str
    email: str

