"""
Summarization endpoints - Skills for Summarization Agent
"""

from fastapi import APIRouter, HTTPException
from app.agents.summarization_agent import SummarizationAgent
from app.agents.base_agent import AgentRequest

router = APIRouter()
summarization_agent = SummarizationAgent()

@router.post("/generate")
async def generate_document(request: AgentRequest):
    """Generate formatted business document"""
    try:
        response = await summarization_agent.execute(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates")
async def list_templates():
    """List available document templates"""
    return {
        "templates": [
            {"type": "brd", "name": "Business Requirements Document"},
            {"type": "minutes", "name": "Meeting Minutes"},
            {"type": "digest", "name": "Email Digest"}
        ]
    }

@router.post("/format")
async def format_document(request: AgentRequest):
    """Format document with style/structure"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


