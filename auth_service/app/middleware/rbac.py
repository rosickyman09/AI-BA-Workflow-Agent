"""
Role-Based Access Control (RBAC) middleware and decorators
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..services.auth_service import verify_token, get_current_user
from ..models import User
import os

# Role hierarchy
ADMIN_ROLES = {"admin"}  # Full access
OPS_ROLES = {"admin", "it"}  # Admin + IT operations
BA_ROLES = {"admin", "ba", "business_owner"}  # Analysts + Business owners
VIEWER_ROLES = {"admin", "ba", "business_owner", "it"}  # Everyone

# Available roles
ALL_ROLES = {"admin", "ba", "business_owner", "it"}


security = HTTPBearer()


def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Extract and verify JWT token, return current user"""
    token = credentials.credentials
    user = get_current_user(db, token)
    return user


def make_require_role(required_roles: List[str]):
    """Create a dependency that requires specific roles"""
    async def role_checker(current_user: User = Depends(get_current_user_from_token)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_roles}, Got: {current_user.role}"
            )
        return current_user
    return role_checker


# Create specific role dependencies
require_admin = make_require_role(["admin"])
require_ba = make_require_role(["admin", "ba", "business_owner"])
require_it = make_require_role(["admin", "it"])


async def require_authenticated(current_user: User = Depends(get_current_user_from_token)) -> User:
    """Require any authenticated user"""
    return current_user


def check_role(user: User, required_roles: List[str]) -> bool:
    """Check if user has any of the required roles"""
    return user.role in required_roles


def check_project_access(user: User, project_id: str) -> bool:
    """Check if user has access to project"""
    # Admin has access to all projects
    if user.role == "admin":
        return True
    
    # Check if user is a member of the project
    for up in user.projects:
        if str(up.project_id) == project_id:
            return True
    
    return False


def check_project_role(user: User, project_id: str, required_roles: List[str]) -> bool:
    """Check if user has a specific role in a project"""
    # Admin has all roles in all projects
    if user.role == "admin":
        return True
    
    # Check user's role in the specific project
    for up in user.projects:
        if str(up.project_id) == project_id:
            return up.role in required_roles
    
    return False

