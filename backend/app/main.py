"""
Backend API Service (Port 5000)
Document orchestration, STT coordination, workflow management
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from datetime import datetime
from .middleware.rbac import (
    get_current_user,
    require_approver,
    require_ba,
    require_readonly,
    TokenUser,
)
from .routers import documents as documents_router
from .routers import approvals as approvals_router
from .routers import notifications as notifications_router
from .routers import projects as projects_router
from .routers import webhooks as webhooks_router
from .routers import knowledge_base as knowledge_base_router
from .routers import urs as urs_router

# Setup structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI BA Agent - Backend API",
    description="Document orchestration and workflow management service",
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(
    documents_router.router,
    prefix="/api/documents",
    tags=["documents"],
)

app.include_router(
    approvals_router.router,
    prefix="/api/approvals",
    tags=["approvals"],
)

app.include_router(
    projects_router.router,
    prefix="/api/projects",
    tags=["projects"],
)

app.include_router(
    notifications_router.router,
    prefix="/api/notifications",
    tags=["notifications"],
)

app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)

app.include_router(
    knowledge_base_router.router,
    prefix="/api/knowledge-base",
    tags=["knowledge-base"],
)

app.include_router(
    urs_router.router,
    prefix="/api/urs",
    tags=["urs"],
)

# ── Health check (no auth required) ──────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Service health check endpoint"""
    return {
        "status": "healthy",
        "service": "backend_api",
        "timestamp": datetime.utcnow().isoformat(),
        "port": 5000
    }

# ── Document endpoints (stub kept for legacy gateway route /api/documents/{doc_id}) ──

@app.get("/api/documents/{doc_id}")
async def get_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_readonly)
):
    """Retrieve document metadata and status. Required: any authenticated role."""
    return {
        "doc_id": doc_id,
        "title": "Sample Document",
        "status": "pending_approval",
        "created_at": datetime.utcnow().isoformat(),
        "requested_by": current_user.email
    }


@app.get("/api/workflow/{workflow_id}")
async def get_workflow_status(
    workflow_id: str,
    current_user: TokenUser = Depends(require_readonly)
):
    """Get workflow processing status. Required: any authenticated role."""
    return {
        "workflow_id": workflow_id,
        "status": "in_progress",
        "current_stage": "extraction",
        "progress": 50
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
