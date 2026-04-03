"""Extraction skills for parsing meeting/business text into entities."""

from __future__ import annotations

import re
from typing import Any, Dict, List


async def extract_entities(text: str, doc_type: str = "meeting") -> Dict[str, Any]:
	data = extract_entities_regex(text)
	data["doc_type"] = doc_type
	return data


def extract_entities_regex(text: str) -> Dict[str, List[Any]]:
	body = text or ""
	lines = [l.strip("- \t") for l in body.splitlines() if l.strip()]

	decisions: List[str] = []
	action_items: List[Dict[str, str]] = []
	requirements: List[Dict[str, str]] = []
	risks: List[str] = []
	stakeholders: List[str] = []

	for line in lines:
		l = line.lower()
		if any(k in l for k in ["agreed", "decision", "approved", "decide"]):
			decisions.append(line)
		if any(k in l for k in ["must", "shall", "requirement", "needs to"]):
			requirements.append({"description": line, "priority": "medium"})
		if any(k in l for k in ["risk", "blocked", "delay", "issue"]):
			risks.append(line)
		if re.search(r"\b(team|owner|admin|ba|it|legal|pm)\b", l):
			stakeholders.append(line)

	if not decisions and body:
		decisions = [body[:240]]
	if not requirements and body:
		requirements = [{"description": body[:200], "priority": "medium"}]

	for d in decisions[:5]:
		action_items.append({"owner": "TBD", "task": d, "due_date": "TBD"})

	return {
		"decisions": decisions,
		"action_items": action_items,
		"requirements": requirements,
		"risks": risks,
		"stakeholders": stakeholders,
	}
