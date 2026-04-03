"""
Workflow orchestration endpoints
"""

from fastapi import APIRouter, HTTPException
from uuid import UUID
from app.agents.routing_agent import RoutingAgent
from app.agents.extraction_agent import DataExtractionAgent
from app.agents.rag_agent import RAGVerificationAgent
from app.agents.summarization_agent import SummarizationAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.security_agent import SecurityAgent
from app.agents.base_agent import AgentRequest

router = APIRouter()

# Initialize all 7 agents
agents = {
    "RoutingAgent": RoutingAgent(),
    "DataExtractionAgent": DataExtractionAgent(),
    "RAGVerificationAgent": RAGVerificationAgent(),
    "SummarizationAgent": SummarizationAgent(),
    "ValidationAgent": ValidationAgent(),
    "MemoryAgent": MemoryAgent(),
    "SecurityAgent": SecurityAgent()
}

@router.post("/execute")
async def execute_workflow(request: AgentRequest):
    """Execute complete workflow (7 agents orchestration)"""
    try:
        # Step 1: Security Agent (entry-point filter)
        security_request = AgentRequest(
            project_id=request.project_id,
            user_id=request.user_id,
            data={"raw_input": str(request.data)}
        )
        security_response = await agents["SecurityAgent"].execute(security_request)
        
        if not security_response.output.get("is_safe"):
            return {"status": "blocked", "reason": "Security threat detected"}
        
        # Step 2: Routing Agent
        routing_response = await agents["RoutingAgent"].execute(request)
        
        # Step 3: Data Extraction Agent
        extraction_response = await agents["DataExtractionAgent"].execute(request)
        
        # Step 4: RAG Verification Agent
        rag_response = await agents["RAGVerificationAgent"].execute(request)
        
        # Step 5: Summarization Agent
        summary_response = await agents["SummarizationAgent"].execute(request)
        
        # Step 6: Validation Agent
        validation_response = await agents["ValidationAgent"].execute(request)
        
        # Step 7: Memory Agent (store context)
        memory_response = await agents["MemoryAgent"].execute(request)
        
        return {
            "workflow_id": "wf-" + str(request.project_id)[:8],
            "status": "completed",
            "agents_executed": 7,
            "steps": {
                "security": security_response.output,
                "routing": routing_response.output,
                "extraction": extraction_response.output,
                "rag_verification": rag_response.output,
                "summarization": summary_response.output,
                "validation": validation_response.output,
                "memory": memory_response.output
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{workflow_id}")
async def get_workflow_status(workflow_id: UUID):
    """Get workflow execution status"""
    # TODO: Query agent_state table
    raise HTTPException(status_code=501, detail="Not implemented yet")

@router.get("/agents")
async def list_agents():
    """List all available agents"""
    return {
        "agents": list(agents.keys()),
        "count": len(agents),
        "description": "7 AI agents in orchestrated pipeline"
    }


