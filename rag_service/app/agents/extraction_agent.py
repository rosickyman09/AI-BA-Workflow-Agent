"""
Agent 2: Data Extraction Agent  Parse Unstructured Content into Structured Entities
"""
import logging
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.skills.extraction_skills import extract_entities, extract_entities_regex
from app.services.db_service import log_agent_state

logger = logging.getLogger(__name__)


class DataExtractionAgent(BaseAgent):
    """Parse transcripts, emails, documents into structured entities."""

    def __init__(self):
        super().__init__("DataExtractionAgent")

    async def execute(self, request: AgentRequest) -> AgentResponse:
        try:
            data = request.data
            doc_type = data.get("doc_type", "meeting")
            transcript = data.get("transcript", data.get("content", ""))

            entities = await self._extract_entities(transcript, doc_type)
            validation = self._validate_extraction(entities)

            confidence = min(1.0, (
                len(entities.get("decisions", [])) * 0.1
                + len(entities.get("action_items", [])) * 0.1
                + len(entities.get("requirements", [])) * 0.1
                + 0.5
            ))

            await log_agent_state(
                workflow_id=data.get("workflow_id", ""),
                agent_name=self.agent_name,
                state_data={"entity_counts": {k: len(v) if isinstance(v, list) else 0
                                               for k, v in entities.items()},
                             "doc_type": doc_type},
                next_agent="RAGVerificationAgent",
            )

            return AgentResponse(
                agent_name=self.agent_name,
                status="success",
                output={"entities": entities, "validation": validation},
                confidence=round(confidence, 2),
            )
        except Exception as e:
            return self.fallback_response(str(e))

    #  Skills 

    async def _extract_entities(self, text: str, doc_type: str) -> dict:
        """Try LLM extraction, fall back to regex heuristics."""
        entities = await extract_entities(text, doc_type)
        if entities.get("_mock") or not any(entities.get(k) for k in ("decisions", "action_items", "requirements")):
            # Augment with regex findings
            regex_entities = extract_entities_regex(text)
            for key in ("decisions", "action_items", "risks"):
                if not entities.get(key) and regex_entities.get(key):
                    entities[key] = regex_entities[key]
        return entities

    def _validate_extraction(self, entities: dict) -> dict:
        """Validate schema compliance  check required keys exist."""
        required = {"decisions", "action_items", "requirements", "risks", "stakeholders"}
        missing = [k for k in required if k not in entities]
        return {"valid": len(missing) == 0, "missing_keys": missing}


