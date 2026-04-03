"""
Base Agent Class - Foundation for all 7 agents
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel

class AgentRequest(BaseModel):
    """Base request for any agent"""
    project_id: str
    user_id: str
    data: Dict[str, Any]

class AgentResponse(BaseModel):
    """Base response from any agent"""
    agent_name: str
    status: str
    output: Dict[str, Any]
    confidence: Optional[float] = None
    error: Optional[str] = None

class BaseAgent:
    """Base agent class with shared functionality"""
    
    def __init__(self, agent_name: str, model_type: str = "primary"):
        self.agent_name = agent_name
        self.model_type = model_type
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Execute agent logic - to be overridden"""
        raise NotImplementedError("Subclasses must implement execute()")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data"""
        return True
    
    def fallback_response(self, error: str) -> AgentResponse:
        """Generate fallback response on error"""
        return AgentResponse(
            agent_name=self.agent_name,
            status="error",
            output={},
            error=error
        )


