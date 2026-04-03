"""
Auth Service (Port 5001)
JWT token generation, user authentication, role-based access control (RBAC)
Real database integration with bcrypt password verification and audit logging
"""

from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import logging
from .database import get_db
from .models import User
from .services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user
)
from .services.audit_service import (
    log_login,
    log_logout,
    log_token_refresh,
    log_failed_login
)
from .middleware.rbac import (
    require_authenticated,
    require_admin,
    require_ba,
    check_role,
    get_current_user_from_token
)
from .routers import users as users_router_module

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI BA Agent - Auth Service",
    description="JWT authentication with real database, bcrypt verification, and RBAC",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router_module.router, prefix="/auth/admin/users", tags=["users"])

security = HTTPBearer()


# Request/Response schemas
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserProfile(BaseModel):
    user_id: str
    email: str
    role: str
    full_name: str | None = None
    projects: list = []


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# Health checks
@app.get("/health")
async def root_health_check():
    """Root health check"""
    return {
        "status": "healthy",
        "service": "auth_service",
        "port": 5001
    }


@app.get("/auth/health")
async def health_check(db: Session = Depends(get_db)):
    """Service health check with database connectivity"""
    try:
        # Verify database connection
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "service": "auth_service",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat(),
        "port": 5001
    }


# Authentication endpoints
@app.post("/auth/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user with email and password.
    Returns JWT access token, refresh token, and user info.
    """
    logger.info(f"Login attempt for user: {request.email}")
    
    # Authenticate against database
    user = authenticate_user(db, request.email, request.password)
    
    if not user:
        # Log failed login
        log_failed_login(
            db=db,
            email=request.email,
            reason="invalid_credentials"
        )
        logger.warning(f"Login failed for user: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        log_failed_login(db=db, email=request.email, reason="account_inactive")
        logger.warning(f"Login blocked for inactive user: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact your administrator."
        )
    
    # Log successful login
    log_login(db=db, user_id=user.user_id, email=user.email)
    
    # Create tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    
    # Get user projects
    projects = [{"project_id": str(up.project_id), "role": up.role} for up in user.projects]
    
    logger.info(f"Successful login for user: {request.email} ({user.user_id})")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=60 * 60,  # 1 hour in seconds
        user={
            "user_id": str(user.user_id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "projects": projects
        }
    )


@app.post("/auth/refresh")
async def refresh_token_endpoint(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Exchange refresh token for new access token.
    Requires valid refresh token.
    """
    try:
        payload = verify_token(request.refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    # Get user from database
    user = get_current_user(db, request.refresh_token)
    
    # Log token refresh
    log_token_refresh(db=db, user_id=user.user_id)
    
    # Create new access token
    new_access_token = create_access_token(user)
    
    logger.info(f"Token refreshed for user: {user.email}")
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": 60 * 60
    }


@app.get("/auth/me")
async def get_profile(
    current_user: User = Depends(require_authenticated)
):
    """
    Get current authenticated user's profile.
    Requires valid JWT token.
    """
    projects = [{"project_id": str(up.project_id), "role": up.role} for up in current_user.projects]
    
    return UserProfile(
        user_id=str(current_user.user_id),
        email=current_user.email,
        role=current_user.role,
        full_name=current_user.full_name,
        projects=projects
    )


@app.post("/auth/logout")
async def logout(
    current_user: User = Depends(require_authenticated),
    db: Session = Depends(get_db)
):
    """
    Logout current user.
    Logs the logout action to audit logs.
    """
    # Log logout
    log_logout(db=db, user_id=current_user.user_id)
    
    logger.info(f"User logged out: {current_user.email}")
    
    return {
        "status": "logged_out",
        "message": "Successfully logged out"
    }


@app.get("/auth/validate")
async def validate_token(
    current_user: User = Depends(require_authenticated)
):
    """
    Validate current JWT token and return user info.
    Used by other services to verify JWT authenticity.
    """
    projects = [{"project_id": str(up.project_id), "role": up.role} for up in current_user.projects]
    
    return {
        "valid": True,
        "sub": str(current_user.user_id),
        "email": current_user.email,
        "role": current_user.role,
        "projects": projects
    }


# Admin endpoints for user management (Phase 2)
@app.get("/auth/users")
async def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users (admin only).
    """
    users = db.query(User).all()
    return [user.to_dict() for user in users]


@app.get("/auth/audit-logs")
async def get_audit_logs(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = 100,
    skip: int = 0
):
    """
    Get audit logs (admin only).
    """
    from .models import AuditLog
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    return [log.to_dict() for log in logs]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)