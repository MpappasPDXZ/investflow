"""Pydantic schemas for user sharing"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserShareCreate(BaseModel):
    """Schema for creating a new share"""
    shared_email: EmailStr = Field(..., description="Email to share with")

class UserShareResponse(BaseModel):
    """Schema for share response"""
    id: str
    user_id: str
    shared_email: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True







