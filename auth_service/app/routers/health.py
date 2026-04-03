"""
Health endpoints
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def health_check():
    return {
        "service": "Auth Service",
        "status": "healthy"
    }
