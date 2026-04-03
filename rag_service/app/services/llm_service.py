"""Minimal LLM service facade used by agent modules."""

from __future__ import annotations

from typing import Any, Dict


async def chat_complete(
	*,
	system_prompt: str,
	user_message: str,
	response_format: str = "text",
) -> Dict[str, Any]:
	"""Return deterministic JSON-style routing output when no external LLM is configured."""
	text = (user_message or "").lower()
	doc_type = "meeting"
	target = "DataExtractionAgent"

	if "brd" in text or "business requirement" in text:
		doc_type = "brd"
	elif "email" in text:
		doc_type = "email"
	elif "requirement" in text or "spec" in text:
		doc_type = "requirements"

	if "search" in text or "similar" in text:
		target = "RAGVerificationAgent"
	elif "summary" in text or "minutes" in text or "brd" in text:
		target = "SummarizationAgent"

	return {
		"target_agent": target,
		"confidence": 0.8,
		"priority": "normal",
		"doc_type": doc_type,
		"_mock": True,
	}
