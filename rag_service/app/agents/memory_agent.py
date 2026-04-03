"""
Agent 6: Memory Agent  Context Management (Redis short-term, PostgreSQL long-term)
"""
import logging
from typing import Dict, Any

from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.services import redis_service
from app.services.db_service import log_agent_state

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    """Manage conversation context, user preferences, and long-term state."""

    def __init__(self):
        super().__init__("MemoryAgent")

    async def execute(self, request: AgentRequest) -> AgentResponse:
        try:
            user_id = request.user_id
            project_id = request.project_id
            data = request.data
            action = data.get("action", "retrieve")  # retrieve | store | clear

            if action == "store":
                payload = data.get("payload", {})
                ok = self._store_context(project_id, user_id, payload)
                output = {"stored": ok, "action": "store"}

            elif action == "clear":
                ok = redis_service.delete_context(project_id, user_id)
                output = {"cleared": ok, "action": "clear"}

            else:  # retrieve
                context = self._retrieve_context(user_id, project_id)
                user_prefs = self._lookup_user_preferences(user_id)
                output = {
                    "context": context,
                    "user_preferences": user_prefs,
                    "action": "retrieve",
                }

                # Also store any new entities passed in this request
                if data.get("entities"):
                    merged = {**context, "latest_entities": data["entities"]}
                    self._store_context(project_id, user_id, merged)

            await log_agent_state(
                workflow_id=data.get("workflow_id", ""),
                agent_name=self.agent_name,
                state_data={"action": action, "project_id": project_id},
                next_agent=None,
            )

            return AgentResponse(
                agent_name=self.agent_name,
                status="success",
                output=output,
                confidence=1.0,
            )
        except Exception as e:
            return self.fallback_response(str(e))

    #  Skills 

    def _retrieve_context(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Read from Redis; return empty dict on miss or error."""
        result = redis_service.get_context(project_id, user_id)
        return result or {}

    def _store_context(self, project_id: str, user_id: str, payload: Dict[str, Any]) -> bool:
        return redis_service.set_context(project_id, user_id, payload, ttl=7200)

    def _lookup_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Cached user preference lookup (fallback to defaults)."""
        cached = redis_service.get_cached(f"user_prefs:{user_id}")
        if cached:
            return cached
        # Defaults  future DB lookup can replace this
        return {"language": "zh-TW", "format": "markdown", "timezone": "Asia/Taipei"}


