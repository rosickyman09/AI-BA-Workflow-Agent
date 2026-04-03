"""
Pydantic Schemas for API Request/Response validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# ============================================================================
# DOCUMENT SCHEMAS
# ============================================================================

class DocumentCreateRequest(BaseModel):
    """Create document request"""
    project_id: UUID
    title: str
    doc_type: str
    
class DocumentResponse(BaseModel):
    """Document response"""
    doc_id: UUID
    project_id: UUID
    title: str
    doc_type: str
    status: str
    upload_time: datetime
    created_by: UUID
    
    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    """List documents response"""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int

# ============================================================================
# APPROVAL SCHEMAS
# ============================================================================

class ApprovalDecisionRequest(BaseModel):
    """Submit approval decision"""
    workflow_id: UUID
    decision: str
    comments: Optional[str] = None

class ApprovalWorkflowResponse(BaseModel):
    """Approval workflow response"""
    workflow_id: UUID
    doc_id: UUID
    current_step: int
    total_steps: int
    status: str
    
    class Config:
        from_attributes = True

class PendingApprovalsResponse(BaseModel):
    """Pending approvals response"""
    workflows: List[ApprovalWorkflowResponse]
    total: int

# ============================================================================
# WORKFLOW SCHEMAS
# ============================================================================

class WorkflowExecuteRequest(BaseModel):
    """Execute workflow request"""
    doc_id: UUID
    workflow_type: str
    
class WorkflowStatusResponse(BaseModel):
    """Workflow status response"""
    workflow_id: UUID
    status: str
    current_step: int
    agent_states: List[dict]
    
    class Config:
        from_attributes = True

# ============================================================================
# HEALTH CHECK
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response"""
    service: str
    status: str
    database: str
    timestamp: datetime
