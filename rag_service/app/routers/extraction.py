"""
Extraction endpoints - Skills for Data Extraction Agent
"""

from fastapi import APIRouter, HTTPException
from app.agents.extraction_agent import DataExtractionAgent
from app.agents.base_agent import AgentRequest

router = APIRouter()
extraction_agent = DataExtractionAgent()

@router.post("/extract")
async def extract_entities(request: AgentRequest):
    """Extract structured entities from unstructured content"""
    try:
        response = await extraction_agent.execute(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transcribe")
async def transcribe_audio(request: AgentRequest):
    """Transcribe audio to text"""
    raise HTTPException(status_code=501, detail="Not implemented yet")

@router.post("/parse-document")
async def parse_document(request: AgentRequest):
    """Parse PDF/DOCX/XLSX files"""
    raise HTTPException(status_code=501, detail="Not implemented yet")

@router.post("/parse-email")
async def parse_email(request: AgentRequest):
    """Parse email threads"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


