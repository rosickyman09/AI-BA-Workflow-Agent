"""
RAG Service (Port 5002)
CrewAI agent orchestration, vector search, embeddings, summarization
Houses 7 AI agents: Security, Routing, Extraction, RAG Verification,
                    Summarization, Validation, Memory
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI BA Agent - RAG Service",
    description="AI agent orchestration with CrewAI, RAG, and LLM integration",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#  Request/Response models 

class DocumentExtractionRequest(BaseModel):
    document_id: str
    project_id: str
    transcript: str
    doc_type: str = "meeting"
    user_id: str = "system"
    workflow_id: str = ""

class RAGSearchRequest(BaseModel):
    project_id: str
    query: str
    top_k: int = 5
    user_id: str = "system"

class SummarizationRequest(BaseModel):
    project_id: str
    entities: dict
    doc_type: str = "minutes"
    user_id: str = "system"
    workflow_id: str = ""

class ValidationRequest(BaseModel):
    project_id: str
    document: Any          # str or dict
    doc_type: str = "default"
    entities: dict = {}
    kb_results: list = []
    user_id: str = "system"
    workflow_id: str = ""

class SecurityCheckRequest(BaseModel):
    user_input: str
    project_id: str = "system"
    user_id: str = "anonymous"

class WorkflowRequest(BaseModel):
    workflow_id: str = ""
    document_id: str = ""
    project_id: str
    user_id: str = "system"
    content: str = ""
    doc_type: str = "meeting"
    extra_data: Dict[str, Any] = {}

class IndexDocumentRequest(BaseModel):
    doc_id: str
    project_id: str
    content: str
    metadata: dict = {}


class EmbedDocumentRequest(BaseModel):
    document_id: str
    project_id: str
    text_content: str
    metadata: dict = {}

#  Health checks 

@app.get("/health")
async def root_health():
    return {"status": "healthy", "service": "rag_service", "port": 5002}

@app.get("/rag/health")
async def rag_health():
    return {
        "status": "healthy",
        "service": "rag_service",
        "timestamp": datetime.utcnow().isoformat(),
        "port": 5002,
        "agents_loaded": 7,
    }

#  Agent endpoints 

@app.post("/rag/security-check")
async def security_check(request: SecurityCheckRequest):
    """Security Agent  detect prompt injection, XSS, and malicious patterns."""
    from app.agents.base_agent import AgentRequest
    from app.agents.security_agent import SecurityAgent

    agent = SecurityAgent()
    resp = await agent.execute(
        AgentRequest(
            project_id=request.project_id,
            user_id=request.user_id,
            data={"raw_input": request.user_input},
        )
    )
    return resp.output


@app.post("/rag/extract")
async def extract_entities(request: DocumentExtractionRequest):
    """Data Extraction Agent  extract decisions, action items, requirements."""
    from app.agents.base_agent import AgentRequest
    from app.agents.security_agent import SecurityAgent
    from app.agents.extraction_agent import DataExtractionAgent

    # Run security check on transcript first
    sec_agent = SecurityAgent()
    sec_resp = await sec_agent.execute(
        AgentRequest(
            project_id=request.project_id,
            user_id=request.user_id,
            data={"raw_input": request.transcript, "workflow_id": request.workflow_id},
        )
    )
    if not sec_resp.output.get("is_safe", True):
        raise HTTPException(status_code=400, detail="Input blocked by security agent")

    agent = DataExtractionAgent()
    resp = await agent.execute(
        AgentRequest(
            project_id=request.project_id,
            user_id=request.user_id,
            data={
                "transcript": sec_resp.output.get("sanitized_input", request.transcript),
                "doc_type": request.doc_type,
                "workflow_id": request.workflow_id,
                "document_id": request.document_id,
            },
        )
    )
    return {
        "document_id": request.document_id,
        "status": "extraction_complete",
        "entities": resp.output.get("entities", {}),
        "validation": resp.output.get("validation", {}),
        "confidence": resp.confidence,
        "agent": resp.agent_name,
    }


@app.post("/rag/search")
async def search_knowledge_base(request: RAGSearchRequest):
    """RAG Verification Agent  semantic search against Qdrant knowledge base."""
    import time
    from app.agents.base_agent import AgentRequest
    from app.agents.rag_agent import RAGVerificationAgent

    t0 = time.time()
    agent = RAGVerificationAgent()
    resp = await agent.execute(
        AgentRequest(
            project_id=request.project_id,
            user_id=request.user_id,
            data={"query": request.query, "entities": {}, "top_k": request.top_k},
        )
    )
    elapsed_ms = round((time.time() - t0) * 1000)
    results = resp.output.get("kb_results", [])
    return {
        "query": request.query,
        "results": results,
        "citations": resp.output.get("citations", []),
        "total_found": len(results),
        "search_time_ms": elapsed_ms,
        "confidence": resp.confidence,
    }


@app.post("/rag/summarize")
async def summarize_document(request: SummarizationRequest):
    """Summarization Agent  generate meeting minutes or BRD from entities."""
    from app.agents.base_agent import AgentRequest
    from app.agents.summarization_agent import SummarizationAgent

    agent = SummarizationAgent()
    resp = await agent.execute(
        AgentRequest(
            project_id=request.project_id,
            user_id=request.user_id,
            data={
                "entities": request.entities,
                "doc_type": request.doc_type,
                "workflow_id": request.workflow_id,
            },
        )
    )
    return {
        "status": "summarization_complete",
        "document": resp.output.get("document", {}),
        "markdown": resp.output.get("markdown", ""),
        "doc_type": request.doc_type,
        "confidence": resp.confidence,
        "format_valid": resp.output.get("format_valid", False),
    }


@app.post("/rag/validate")
async def validate_document(request: ValidationRequest):
    """Validation Agent  quality gate, risk detection, completeness check."""
    from app.agents.base_agent import AgentRequest
    from app.agents.validation_agent import ValidationAgent

    agent = ValidationAgent()
    resp = await agent.execute(
        AgentRequest(
            project_id=request.project_id,
            user_id=request.user_id,
            data={
                "document": request.document,
                "doc_type": request.doc_type,
                "entities": request.entities,
                "kb_results": request.kb_results,
                "workflow_id": request.workflow_id,
            },
        )
    )
    return {
        "status": "validation_complete",
        "compliant": resp.output.get("compliant", True),
        "risk_flags": resp.output.get("risk_flags", []),
        "hitl_required": resp.output.get("hitl_required", False),
        "completeness": resp.output.get("completeness", {}),
        "confidence": resp.confidence,
        "ready_for_approval": not resp.output.get("hitl_required", False),
    }


@app.get("/rag/memory/{user_id}")
async def get_user_context(user_id: str, project_id: str):
    """Memory Agent  retrieve user context and preferences from Redis."""
    from app.agents.base_agent import AgentRequest
    from app.agents.memory_agent import MemoryAgent

    agent = MemoryAgent()
    resp = await agent.execute(
        AgentRequest(
            project_id=project_id,
            user_id=user_id,
            data={"action": "retrieve"},
        )
    )
    return {
        "user_id": user_id,
        "project_id": project_id,
        "context": resp.output.get("context", {}),
        "preferences": resp.output.get("user_preferences", {}),
    }


@app.post("/rag/documents/index")
async def index_document(request: IndexDocumentRequest):
    """Index a document's text chunks into the Qdrant knowledge base."""
    from app.skills.rag_skills import index_document as _index

    count = await _index(
        doc_id=request.doc_id,
        content=request.content,
        project_id=request.project_id,
        metadata=request.metadata,
    )
    return {"doc_id": request.doc_id, "chunks_indexed": count, "status": "indexed" if count > 0 else "empty"}


@app.post("/rag/embed")
async def embed_document(request: EmbedDocumentRequest):
    """Embed and index a document into project-scoped Qdrant collection."""
    from app.skills.rag_skills import index_document as _index

    count = await _index(
        doc_id=request.document_id,
        content=request.text_content,
        project_id=request.project_id,
        metadata=request.metadata,
    )
    return {
        "status": "embedded" if count > 0 else "empty",
        "document_id": request.document_id,
        "project_id": request.project_id,
        "chunks": count,
    }


#  Full pipeline workflow 

@app.post("/rag/workflow/execute")
async def execute_workflow(request: WorkflowRequest):
    """Run the full 7-agent pipeline sequentially."""
    from app.services.crewai_orchestrator import get_pipeline
    import psycopg2
    from app.config import settings

    workflow_id = request.workflow_id
    if not workflow_id and request.document_id:
        conn = None
        cur = None
        try:
            try:
                conn = psycopg2.connect(settings.DATABASE_URL)
            except Exception:
                db_host = os.environ.get("DB_HOST", "postgres")
                db_port = os.environ.get("DB_PORT", "5432")
                db_name = os.environ.get("DB_NAME", "ai_ba_db")
                db_user = os.environ.get("DB_USER", "postgres")
                db_password = os.environ.get("DB_PASSWORD", "postgres")
                fallback_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                conn = psycopg2.connect(fallback_url)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT workflow_id
                FROM approval_workflows
                WHERE doc_id = %s::uuid
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (request.document_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                workflow_id = str(row[0])
        except Exception as exc:
            logger.warning("Failed to resolve workflow_id from document_id=%s: %s", request.document_id, exc)
        finally:
            if cur is not None:
                cur.close()
            if conn is not None:
                conn.close()

    if not workflow_id:
        raise HTTPException(status_code=422, detail="workflow_id is required or resolvable from document_id")

    pipeline = get_pipeline()
    result = await pipeline.run(
        workflow_id=workflow_id,
        project_id=request.project_id,
        user_id=request.user_id,
        content=request.content,
        doc_type=request.doc_type,
        extra_data=request.extra_data,
    )
    return result.to_dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)


