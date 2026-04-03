"""
Auth Service Schemas
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

class LoginRequest(BaseModel):
    """User login request"""
    email: str
    password: str

class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class UserResponse(BaseModel):
    """User response"""
    user_id: UUID
    email: str
    role: str
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

class UserCreateRequest(BaseModel):
    """Create user request"""
    email: str
    password: str
    role: str = "ba"
    full_name: Optional[str] = None

class UserUpdateRequest(BaseModel):
    """Update user request (admin only)"""
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None  # if provided, will be re-hashed
