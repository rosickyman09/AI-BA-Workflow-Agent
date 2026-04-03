"""
Agent 5: Validation Agent  Quality Gate & Risk Detection
"""
import logging
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.skills.validation_skills import (
    check_risk_flags, requires_human_review, check_completeness, calculate_confidence
)
from app.services.db_service import log_agent_state

logger = logging.getLogger(__name__)


class ValidationAgent(BaseAgent):
    """Quality gate  validate document and assign risk flags."""

    def __init__(self):
        super().__init__("ValidationAgent")

    async def execute(self, request: AgentRequest) -> AgentResponse:
        try:
            data = request.data
            document = data.get("document", data.get("markdown", ""))
            doc_type = data.get("doc_type", "default")
            entities = data.get("entities", {})
            kb_results = data.get("kb_results", [])

            # Convert dict documents to string for text scanning
            if isinstance(document, dict):
                import json
                scan_text = json.dumps(document, ensure_ascii=False)
            else:
                scan_text = str(document)

            risk_flags = check_risk_flags(scan_text)
            hitl_required = requires_human_review(risk_flags)
            completeness = check_completeness(document if isinstance(document, dict) else {}, doc_type)
            confidence = calculate_confidence(entities, risk_flags, kb_results)

            await log_agent_state(
                workflow_id=data.get("workflow_id", ""),
                agent_name=self.agent_name,
                state_data={
                    "risk_flag_count": len(risk_flags),
                    "hitl_required": hitl_required,
                    "completeness_score": completeness["score"],
                    "confidence": confidence,
                },
                next_agent="MemoryAgent",
            )

            return AgentResponse(
                agent_name=self.agent_name,
                status="success",
                output={
                    "compliant": completeness["complete"],
                    "risk_flags": risk_flags,
                    "hitl_required": hitl_required,
                    "completeness": completeness,
                    "format_valid": bool(scan_text and len(scan_text) > 20),
                },
                confidence=confidence,
            )
        except Exception as e:
            return self.fallback_response(str(e))


