"""
Health endpoints
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def health_check():
    return {
        "service": "RAG Service",
        "status": "healthy",
        "agents": 7,
        "skills": 33
    }


