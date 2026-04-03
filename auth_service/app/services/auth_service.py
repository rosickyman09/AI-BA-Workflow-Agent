"""
Authentication service with bcrypt password verification and JWT generation
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status
import os
from ..models import User, UserProject, Project
import uuid

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.environ.get("JWT_EXPIRY_MINUTES", "60"))
JWT_REFRESH_EXPIRY_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRY_DAYS", "30"))


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with user data and projects"""
    # Get user projects
    projects = [{"project_id": str(up.project_id), "role": up.role} for up in user.projects]
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRY_MINUTES)
    
    to_encode = {
        "sub": str(user.user_id),  # user_id
        "email": user.email,
        "role": user.role,
        "projects": projects,
        "exp": expire
    }
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(user: User) -> str:
    """Create JWT refresh token with longer expiry"""
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_EXPIRY_DAYS)
    to_encode = {
        "sub": str(user.user_id),
        "email": user.email,
        "type": "refresh",
        "exp": expire
    }
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password from database"""
    # Query user from database
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        return None
    
    # Verify password against stored hash
    if not verify_password(password, user.password_hash):
        return None
    
    return user


def refresh_access_token(token: str, db: Session) -> str:
    """Create new access token from refresh token"""
    payload = verify_token(token)
    
    # Check if it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user_id = UUID(payload.get("sub"))
    user = db.query(User).filter(User.user_id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create new access token
    return create_access_token(user)


def get_current_user(db: Session, token: str) -> User:
    """Get current user from JWT token"""
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.user_id == UUID(user_id)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


from uuid import UUID
