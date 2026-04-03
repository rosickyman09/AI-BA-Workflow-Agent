"""
Validation endpoints - Skills for Validation Agent
"""

from fastapi import APIRouter, HTTPException
from app.agents.validation_agent import ValidationAgent
from app.agents.base_agent import AgentRequest

router = APIRouter()
validation_agent = ValidationAgent()

@router.post("/validate")
async def validate_document(request: AgentRequest):
    """Validate document and assign risk flags"""
    try:
        response = await validation_agent.execute(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk-assessment")
async def assess_risks(request: AgentRequest):
    """Assess document risk level"""
    raise HTTPException(status_code=501, detail="Not implemented yet")

@router.post("/compliance-check")
async def check_compliance(request: AgentRequest):
    """Check compliance with rules"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


