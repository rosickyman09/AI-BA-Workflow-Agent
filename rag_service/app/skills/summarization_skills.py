"""Summarization skills to generate business-ready document structures."""

from __future__ import annotations

from typing import Any, Dict, List


def _as_list(value: Any) -> List[Any]:
	return value if isinstance(value, list) else []


async def generate_meeting_minutes(entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
	decisions = _as_list(entities.get("decisions"))
	actions = _as_list(entities.get("action_items"))
	risks = _as_list(entities.get("risks"))
	citations = _as_list((context or {}).get("citations"))

	return {
		"title": "Meeting Minutes",
		"summary": decisions[0] if decisions else "Summary unavailable",
		"decisions": decisions,
		"action_items": actions,
		"risks": risks,
		"citations": citations,
	}


async def generate_brd(entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
	reqs = _as_list(entities.get("requirements"))
	risks = _as_list(entities.get("risks"))
	citations = _as_list((context or {}).get("citations"))

	return {
		"title": "Business Requirements Document",
		"business_objective": "Define and deliver agreed business capabilities.",
		"functional_requirements": reqs,
		"risks": risks,
		"citations": citations,
	}


def render_as_markdown(document: Dict[str, Any], doc_type: str) -> str:
	title = document.get("title", "Generated Document")
	lines: List[str] = [f"# {title}"]

	if document.get("summary"):
		lines += ["", "## Summary", str(document["summary"])]

	if document.get("business_objective"):
		lines += ["", "## Business Objective", str(document["business_objective"])]

	if isinstance(document.get("decisions"), list):
		lines += ["", "## Decisions"]
		for item in document["decisions"]:
			lines.append(f"- {item}")

	if isinstance(document.get("functional_requirements"), list):
		lines += ["", "## Functional Requirements"]
		for item in document["functional_requirements"]:
			if isinstance(item, dict):
				lines.append(f"- {item.get('description', 'N/A')}")
			else:
				lines.append(f"- {item}")

	if isinstance(document.get("action_items"), list):
		lines += ["", "## Action Items"]
		for item in document["action_items"]:
			if isinstance(item, dict):
				lines.append(f"- {item.get('task', 'N/A')} (owner: {item.get('owner', 'TBD')})")
			else:
				lines.append(f"- {item}")

	if isinstance(document.get("risks"), list) and document["risks"]:
		lines += ["", "## Risks"]
		for item in document["risks"]:
			lines.append(f"- {item}")

	if isinstance(document.get("citations"), list) and document["citations"]:
		lines += ["", "## Citations"]
		for item in document["citations"]:
			lines.append(f"- {item}")

	return "\n".join(lines).strip()
