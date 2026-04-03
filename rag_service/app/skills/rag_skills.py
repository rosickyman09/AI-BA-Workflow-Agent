"""RAG skills: indexing, semantic search, and source citation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.embedding_service import embed_query, embed_texts, section_aware_chunk_text
from app.services.vector_db_service import search_project, upsert_document_chunks


async def index_document(
	*,
	doc_id: str,
	content: str,
	project_id: str,
	metadata: Optional[Dict[str, Any]] = None,
) -> int:
	chunks = section_aware_chunk_text(content, chunk_size=512, overlap=50)
	if not chunks:
		return 0

	vectors = embed_texts([c["text"] for c in chunks])
	return upsert_document_chunks(
		project_id=project_id,
		doc_id=doc_id,
		chunks=chunks,
		vectors=vectors,
		metadata=metadata,
	)


async def semantic_search(query: str, project_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
	if not query or not query.strip():
		return []

	query_vector = embed_query(query)
	return search_project(
		project_id=project_id,
		query_vector=query_vector,
		query_text=query,
		top_k=max(1, top_k),
		confidence_threshold=0.6,
	)


def generate_citations(kb_results: List[Dict[str, Any]]) -> List[str]:
	seen = set()
	citations: List[str] = []
	for item in kb_results:
		citation = item.get("citation")
		if citation and citation not in seen:
			seen.add(citation)
			citations.append(citation)
	return citations
