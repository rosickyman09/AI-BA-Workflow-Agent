"""
Agent 1: Routing Agent  Request Classification
"""
import logging
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.services.llm_service import chat_complete
from app.services.db_service import log_agent_state

logger = logging.getLogger(__name__)

_ROUTE_SYSTEM = """You are a request router for an AI BA (Business Analyst) system.
Given a document request, respond in JSON with:
- target_agent: one of [DataExtractionAgent, RAGVerificationAgent, SummarizationAgent]
- confidence: float 0-1
- priority: one of [urgent, high, normal, low]
- doc_type: meeting | email | brd | requirements | other
Return ONLY valid JSON."""

# Keyword fallback map (doc_type heuristic w/o LLM)
_DOC_TYPE_KEYWORDS = {
    "meeting": ["meeting", "minutes", "standup", "scrum", "conference", ""],
    "email": ["email", "mail", "re:", "fwd:", ""],
    "brd": ["brd", "business requirement", ""],
    "requirements": ["requirement", "spec", "feature", "user story", ""],
}


class RoutingAgent(BaseAgent):
    """Request classifier  routes to appropriate specialist agent."""

    def __init__(self):
        super().__init__("RoutingAgent")

    async def execute(self, request: AgentRequest) -> AgentResponse:
        try:
            data = request.data
            text = data.get("transcript", data.get("content", ""))
            doc_type_hint = data.get("doc_type", "")

            classification = await self._classify_request(text, doc_type_hint)
            metadata = self._extract_metadata(data)

            await log_agent_state(
                workflow_id=data.get("workflow_id", ""),
                agent_name=self.agent_name,
                state_data={"classification": classification, "metadata": metadata},
                next_agent=classification.get("target_agent"),
            )

            return AgentResponse(
                agent_name=self.agent_name,
                status="success",
                output={
                    "target_agent": classification.get("target_agent", "DataExtractionAgent"),
                    "confidence": classification.get("confidence", 0.8),
                    "priority": classification.get("priority", "normal"),
                    "doc_type": classification.get("doc_type", doc_type_hint or "other"),
                    "metadata": metadata,
                },
                confidence=classification.get("confidence", 0.8),
            )
        except Exception as e:
            return self.fallback_response(str(e))

    #  Skills 

    async def _classify_request(self, text: str, doc_type_hint: str) -> dict:
        """LLM classification with keyword fallback."""
        user_msg = f"doc_type_hint: {doc_type_hint}\n\nContent snippet:\n{text[:2000]}"
        result = await chat_complete(
            system_prompt=_ROUTE_SYSTEM,
            user_message=user_msg,
            response_format="json",
        )
        if result.get("_mock"):
            # Keyword fallback
            detected = self._keyword_classify(text or doc_type_hint)
            result["doc_type"] = detected
            result["target_agent"] = "DataExtractionAgent"
        return result

    def _keyword_classify(self, text: str) -> str:
        lower = text.lower()
        for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
            if any(k in lower for k in keywords):
                return doc_type
        return "other"

    def _extract_metadata(self, data: dict) -> dict:
        return {
            "doc_type": data.get("doc_type", "other"),
            "file_size": len(str(data.get("transcript", data.get("content", "")))),
            "has_audio": data.get("doc_type") == "audio",
        }


