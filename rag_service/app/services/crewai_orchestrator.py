"""Lightweight async orchestrator for the 7-agent RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict
import time

from app.agents.base_agent import AgentRequest
from app.agents.security_agent import SecurityAgent
from app.agents.routing_agent import RoutingAgent
from app.agents.extraction_agent import DataExtractionAgent
from app.agents.rag_agent import RAGVerificationAgent
from app.agents.summarization_agent import SummarizationAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.memory_agent import MemoryAgent


@dataclass
class PipelineResult:
	workflow_id: str
	project_id: str
	status: str
	duration_ms: int
	outputs: Dict[str, Any]
	error: str | None = None

	def to_dict(self) -> Dict[str, Any]:
		return {
			"workflow_id": self.workflow_id,
			"project_id": self.project_id,
			"status": self.status,
			"duration_ms": self.duration_ms,
			"outputs": self.outputs,
			"error": self.error,
			"timestamp": datetime.utcnow().isoformat(),
		}


class CrewAIPipeline:
	def __init__(self) -> None:
		self.security = SecurityAgent()
		self.routing = RoutingAgent()
		self.extraction = DataExtractionAgent()
		self.rag = RAGVerificationAgent()
		self.summarization = SummarizationAgent()
		self.validation = ValidationAgent()
		self.memory = MemoryAgent()

	async def run(
		self,
		*,
		workflow_id: str,
		project_id: str,
		user_id: str,
		content: str,
		doc_type: str = "meeting",
		extra_data: Dict[str, Any] | None = None,
	) -> PipelineResult:
		t0 = time.perf_counter()
		payload: Dict[str, Any] = {
			"workflow_id": workflow_id,
			"doc_type": doc_type,
			"content": content,
			**(extra_data or {}),
		}
		outputs: Dict[str, Any] = {}

		try:
			security_resp = await self.security.execute(
				AgentRequest(project_id=project_id, user_id=user_id, data={"raw_input": content, "workflow_id": workflow_id})
			)
			outputs["security"] = security_resp.output
			if not security_resp.output.get("is_safe", True):
				return PipelineResult(
					workflow_id=workflow_id,
					project_id=project_id,
					status="blocked",
					duration_ms=int((time.perf_counter() - t0) * 1000),
					outputs=outputs,
					error="Input blocked by security agent",
				)

			sanitized = security_resp.output.get("sanitized_input", content)
			payload["content"] = sanitized
			payload["transcript"] = sanitized

			routing_resp = await self.routing.execute(
				AgentRequest(project_id=project_id, user_id=user_id, data=payload)
			)
			outputs["routing"] = routing_resp.output

			extraction_resp = await self.extraction.execute(
				AgentRequest(project_id=project_id, user_id=user_id, data=payload)
			)
			outputs["extraction"] = extraction_resp.output

			rag_data = {
				**payload,
				"entities": extraction_resp.output.get("entities", {}),
				"query": sanitized,
			}
			rag_resp = await self.rag.execute(
				AgentRequest(project_id=project_id, user_id=user_id, data=rag_data)
			)
			outputs["rag"] = rag_resp.output

			summary_data = {
				**payload,
				"entities": extraction_resp.output.get("entities", {}),
				"verified_content": rag_resp.output.get("verified", {}),
				"context": {
					"kb_results": rag_resp.output.get("kb_results", []),
					"citations": rag_resp.output.get("citations", []),
				},
			}
			summary_resp = await self.summarization.execute(
				AgentRequest(project_id=project_id, user_id=user_id, data=summary_data)
			)
			outputs["summarization"] = summary_resp.output

			validation_data = {
				**payload,
				"document": summary_resp.output.get("document", {}),
				"markdown": summary_resp.output.get("markdown", ""),
				"entities": extraction_resp.output.get("entities", {}),
				"kb_results": rag_resp.output.get("kb_results", []),
			}
			validation_resp = await self.validation.execute(
				AgentRequest(project_id=project_id, user_id=user_id, data=validation_data)
			)
			outputs["validation"] = validation_resp.output

			_ = await self.memory.execute(
				AgentRequest(
					project_id=project_id,
					user_id=user_id,
					data={
						"action": "store",
						"workflow_id": workflow_id,
						"payload": {
							"workflow_id": workflow_id,
							"doc_type": doc_type,
							"validation": validation_resp.output,
						},
					},
				)
			)

			return PipelineResult(
				workflow_id=workflow_id,
				project_id=project_id,
				status="completed",
				duration_ms=int((time.perf_counter() - t0) * 1000),
				outputs=outputs,
			)
		except Exception as exc:
			return PipelineResult(
				workflow_id=workflow_id,
				project_id=project_id,
				status="failed",
				duration_ms=int((time.perf_counter() - t0) * 1000),
				outputs=outputs,
				error=str(exc),
			)


_PIPELINE = CrewAIPipeline()


def get_pipeline() -> CrewAIPipeline:
	return _PIPELINE
