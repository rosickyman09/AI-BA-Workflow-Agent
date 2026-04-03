"""
Agent 3: RAG Verification Agent  Ground Entities in Knowledge Base
"""
import logging
from typing import List, Dict, Any

from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.skills.rag_skills import semantic_search, generate_citations
from app.services.db_service import log_agent_state

logger = logging.getLogger(__name__)


class RAGVerificationAgent(BaseAgent):
    """Ground claims in knowledge base and generate citations."""

    def __init__(self):
        super().__init__("RAGVerificationAgent")

    async def execute(self, request: AgentRequest) -> AgentResponse:
        try:
            data = request.data
            entities = data.get("entities", {})
            query = data.get("query", self._entities_to_query(entities))
            project_id = request.project_id
            top_k = int(data.get("top_k", 5))

            kb_results = await self._semantic_search(query, project_id, top_k)
            citations = generate_citations(kb_results)
            confidence = self._score_confidence(kb_results)

            await log_agent_state(
                workflow_id=data.get("workflow_id", ""),
                agent_name=self.agent_name,
                state_data={"kb_hits": len(kb_results), "citations": len(citations)},
                next_agent="SummarizationAgent",
            )

            return AgentResponse(
                agent_name=self.agent_name,
                status="success",
                output={
                    "verified": entities,
                    "kb_results": kb_results,
                    "citations": citations,
                    "grounded": bool(kb_results),
                },
                confidence=confidence,
            )
        except Exception as e:
            return self.fallback_response(str(e))

    #  Skills 

    async def _semantic_search(self, query: str, project_id: str, top_k: int) -> List[Dict[str, Any]]:
        return await semantic_search(query, project_id=project_id, top_k=top_k)

    def _entities_to_query(self, entities: dict) -> str:
        """Build a query string from entity list for similarity search."""
        parts = []
        for decision in entities.get("decisions", [])[:3]:
            parts.append(str(decision))
        for req in entities.get("requirements", [])[:3]:
            desc = req.get("description", str(req)) if isinstance(req, dict) else str(req)
            parts.append(desc)
        return " ".join(parts) if parts else "project requirements"

    def _score_confidence(self, kb_results: List[Dict[str, Any]]) -> float:
        if not kb_results:
            return 0.0
        top_score = max(r.get("score", 0) for r in kb_results)
        return round(min(top_score, 1.0), 2)


