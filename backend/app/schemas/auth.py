"""Authentication schemas"""
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """User registration schema"""
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    tax_rate: float | None = Field(None, ge=0, le=1, description="Tax rate as decimal (e.g., 0.22 for 22%)")


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr = Field(
        example="john.doe@example.com",
        description="User email address"
    )
    password: str = Field(
        example="password123",
        description="User password"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "john.doe@example.com",
                    "password": "password123"
                }
            ]
        }
    }


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token data schema"""
    user_id: str
    email: str

