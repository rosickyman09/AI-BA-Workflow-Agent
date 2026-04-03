"""
Health check endpoints
"""

from fastapi import APIRouter, Depends
from datetime import datetime
from app.schemas import HealthCheckResponse

router = APIRouter()

@router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """Simple health check"""
    return HealthCheckResponse(
        service="Backend API",
        status="healthy",
        database="connected",
        timestamp=datetime.now()
    )
