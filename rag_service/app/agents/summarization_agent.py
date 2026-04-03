"""
Agent 4: Summarization Agent  Generate Business Documents (BRD / Meeting Minutes)
"""
import logging
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.skills.summarization_skills import generate_meeting_minutes, generate_brd, render_as_markdown
from app.services.db_service import log_agent_state

logger = logging.getLogger(__name__)


class SummarizationAgent(BaseAgent):
    """Generate formatted business documents from verified entities."""

    def __init__(self):
        super().__init__("SummarizationAgent")

    async def execute(self, request: AgentRequest) -> AgentResponse:
        try:
            data = request.data
            entities = data.get("entities", data.get("verified_content", {}))
            doc_type = data.get("doc_type", "minutes")
            context = data.get("context", {})

            document = await self._generate_document(entities, doc_type, context)
            markdown = render_as_markdown(document, doc_type)

            await log_agent_state(
                workflow_id=data.get("workflow_id", ""),
                agent_name=self.agent_name,
                state_data={
                    "doc_type": doc_type,
                    "markdown_len": len(markdown),
                    "markdown": markdown,
                    "document": document,
                },
                next_agent="ValidationAgent",
            )

            return AgentResponse(
                agent_name=self.agent_name,
                status="success",
                output={
                    "document": document,
                    "markdown": markdown,
                    "doc_type": doc_type,
                    "format_valid": bool(markdown and len(markdown) > 20),
                },
                confidence=0.85,
            )
        except Exception as e:
            return self.fallback_response(str(e))

    #  Skills 

    async def _generate_document(self, entities: dict, doc_type: str, context: dict) -> dict:
        if doc_type in ("minutes", "meeting"):
            return await generate_meeting_minutes(entities, context)
        else:
            return await generate_brd(entities, context)


