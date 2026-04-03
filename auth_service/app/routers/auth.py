"""
Auth endpoints
"""

from fastapi import APIRouter, HTTPException
from app.schemas import LoginRequest, TokenResponse, UserResponse

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """User login"""
    # TODO: Implement JWT generation
    raise HTTPException(status_code=501, detail="Not implemented yet")

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token"""
    # TODO: Implement token refresh
    raise HTTPException(status_code=501, detail="Not implemented yet")

@router.post("/logout")
async def logout():
    """User logout"""
    # TODO: Implement logout (invalidate token)
    raise HTTPException(status_code=501, detail="Not implemented yet")

@router.get("/me", response_model=UserResponse)
async def get_current_user():
    """Get current user info"""
    # TODO: Get from decoded JWT
    raise HTTPException(status_code=501, detail="Not implemented yet")
