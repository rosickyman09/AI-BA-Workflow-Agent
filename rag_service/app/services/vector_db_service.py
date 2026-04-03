"""Qdrant vector store service for project-scoped semantic retrieval."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings


CONFIDENCE_THRESHOLD = 0.6


_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
	global _client
	if _client is None:
		_client = QdrantClient(
			host=settings.QDRANT_HOST,
			port=settings.QDRANT_PORT,
			timeout=settings.QDRANT_TIMEOUT,
			check_compatibility=False,
		)
	return _client


def collection_name(project_id: str) -> str:
	safe = re.sub(r"[^a-zA-Z0-9]+", "_", str(project_id)).strip("_").lower()
	return f"project_{safe}"[:63]


def ensure_project_collection(project_id: str) -> str:
	name = collection_name(project_id)
	client = get_client()

	collections = client.get_collections().collections
	existing = {c.name for c in collections}
	if name not in existing:
		client.create_collection(
			collection_name=name,
			vectors_config=qmodels.VectorParams(
				size=settings.EMBEDDING_DIMENSION,
				distance=qmodels.Distance.COSINE,
			),
		)

	return name


def upsert_document_chunks(
	*,
	project_id: str,
	doc_id: str,
	chunks: List[Dict[str, Any]],
	vectors: List[List[float]],
	metadata: Optional[Dict[str, Any]] = None,
) -> int:
	if not chunks or not vectors or len(chunks) != len(vectors):
		return 0

	name = ensure_project_collection(project_id)
	client = get_client()
	base_metadata = metadata or {}

	points: List[qmodels.PointStruct] = []
	now_iso = datetime.utcnow().isoformat()

	for chunk, vector in zip(chunks, vectors):
		payload = {
			"project_id": str(project_id),
			"doc_id": str(doc_id),
			"section": chunk.get("section", "section"),
			"text": chunk.get("text", ""),
			"page": chunk.get("page"),
			"source": chunk.get("source", "document"),
			"created_at": now_iso,
		}
		payload.update(base_metadata)

		points.append(
			qmodels.PointStruct(
				id=str(uuid4()),
				vector=vector,
				payload=payload,
			)
		)

	client.upsert(collection_name=name, points=points, wait=True)
	return len(points)


def search_project(
	*,
	project_id: str,
	query_vector: List[float],
	query_text: str,
	top_k: int = 5,
	confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> List[Dict[str, Any]]:
	if not query_vector:
		return []

	name = collection_name(project_id)
	client = get_client()
	collections = client.get_collections().collections
	if name not in {c.name for c in collections}:
		return []

	expanded_k = max(top_k * 3, top_k)
	filter_clause = qmodels.Filter(
		must=[
			qmodels.FieldCondition(
				key="project_id",
				match=qmodels.MatchValue(value=str(project_id)),
			)
		]
	)

	response = client.query_points(
		collection_name=name,
		query=query_vector,
		query_filter=filter_clause,
		limit=expanded_k,
		with_payload=True,
	)

	reranked = _rerank_results(response.points, query_text)
	filtered = [item for item in reranked if item["score"] >= confidence_threshold]
	return filtered[:top_k]


def _rerank_results(raw_hits: List[Any], query_text: str) -> List[Dict[str, Any]]:
	query_terms = _terms(query_text)
	ranked: List[Dict[str, Any]] = []

	for hit in raw_hits:
		payload = hit.payload or {}
		text = str(payload.get("text", ""))
		doc_id = str(payload.get("doc_id", "unknown"))
		section = str(payload.get("section", "section"))
		vector_score = float(hit.score or 0.0)

		lexical_score = _lexical_overlap(query_terms, _terms(text))
		# Lexical boost improves precision when embedding backend falls back.
		boost = 0.1 if lexical_score >= 0.6 else 0.0
		final_score = round(min(1.0, 0.5 * vector_score + 0.5 * lexical_score + boost), 4)

		ranked.append(
			{
				"text": text,
				"score": final_score,
				"vector_score": round(vector_score, 4),
				"lexical_score": round(lexical_score, 4),
				"doc_id": doc_id,
				"section": section,
				"page": payload.get("page"),
				"source": payload.get("source", "document"),
				"citation": f"[{doc_id}#{section}]",
			}
		)

	ranked.sort(key=lambda x: x["score"], reverse=True)
	return ranked


def _terms(text: str) -> set[str]:
	return {tok for tok in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(tok) > 2}


def _lexical_overlap(query_terms: set[str], text_terms: set[str]) -> float:
	if not query_terms:
		return 0.0
	return len(query_terms.intersection(text_terms)) / max(len(query_terms), 1)
