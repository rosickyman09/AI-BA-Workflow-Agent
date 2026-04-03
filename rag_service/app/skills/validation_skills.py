"""Validation skills for risk detection and quality scoring."""

from __future__ import annotations

import re
from typing import Any, Dict, List


def check_risk_flags(text: str) -> List[Dict[str, Any]]:
	body = (text or "").lower()
	flags: List[Dict[str, Any]] = []

	legal_terms = ["contract", "legal", "liability", "compliance"]
	finance_terms = ["budget", "cost", "price", "financial", "usd", "ntd"]

	if any(k in body for k in legal_terms):
		flags.append({"type": "legal", "severity": "high", "reason": "Legal terms detected"})
	if any(k in body for k in finance_terms) or re.search(r"\b\d+[\.,]?\d*\b", body):
		flags.append({"type": "financial", "severity": "high", "reason": "Financial signal detected"})
	return flags


def requires_human_review(risk_flags: List[Dict[str, Any]]) -> bool:
	return len(risk_flags) > 0


def check_completeness(document: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
	required = ["title"]
	if doc_type in ("meeting", "minutes"):
		required += ["summary", "decisions"]
	else:
		required += ["business_objective"]

	present = sum(1 for k in required if document.get(k))
	score = round((present / max(1, len(required))) * 100, 2)
	return {
		"required_fields": required,
		"present_fields": present,
		"score": score,
		"complete": present == len(required),
	}


def calculate_confidence(entities: Dict[str, Any], risk_flags: List[Dict[str, Any]], kb_results: List[Dict[str, Any]]) -> float:
	base = 0.7
	if entities:
		base += 0.1
	if kb_results:
		base += 0.1
	if risk_flags:
		base -= 0.1
	return round(max(0.0, min(1.0, base)), 2)
