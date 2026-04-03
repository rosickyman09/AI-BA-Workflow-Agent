"""Embedding service using sentence-transformers with section-aware chunking."""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
import logging
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


TOKEN_CHUNK_SIZE = 512
TOKEN_OVERLAP = 50


@lru_cache(maxsize=1)
def _get_model() -> Optional[Any]:
	try:
		from sentence_transformers import SentenceTransformer

		return SentenceTransformer(settings.EMBEDDING_MODEL)
	except Exception as exc:
		logger.warning("sentence_transformers_unavailable: %s", exc)
		return None


def embed_texts(texts: List[str]) -> List[List[float]]:
	if not texts:
		return []
	model = _get_model()
	if model is not None:
		vectors = model.encode(texts, normalize_embeddings=True)
		return [v.tolist() for v in vectors]
	return [_fallback_embed(text) for text in texts]


def embed_query(query: str) -> List[float]:
	vectors = embed_texts([query])
	return vectors[0] if vectors else []


def section_aware_chunk_text(
	text: str,
	chunk_size: int = TOKEN_CHUNK_SIZE,
	overlap: int = TOKEN_OVERLAP,
) -> List[Dict[str, Any]]:
	if not text or not text.strip():
		return []

	sections = _split_sections(text)
	chunks: List[Dict[str, Any]] = []

	for section in sections:
		section_name = section["section"]
		body = section["text"]
		tokens = body.split()
		if not tokens:
			continue

		idx = 1
		start = 0
		n = len(tokens)

		while start < n:
			end = min(start + chunk_size, n)
			chunk_tokens = tokens[start:end]
			chunk_text = " ".join(chunk_tokens).strip()
			if chunk_text:
				chunk_section = section_name if n <= chunk_size else f"{section_name}.{idx}"
				chunks.append(
					{
						"section": chunk_section,
						"text": chunk_text,
						"page": None,
						"source": "document",
					}
				)
			if end >= n:
				break
			start = max(0, end - overlap)
			idx += 1

	return chunks


def _split_sections(text: str) -> List[Dict[str, str]]:
	lines = text.splitlines()
	sections: List[Dict[str, str]] = []
	current_title = "section_1"
	current_lines: List[str] = []
	section_index = 1

	heading_pattern = re.compile(r"^\s{0,3}(#{1,6}\s+.+|\d+(\.\d+)*\s+.+)$")

	def flush() -> None:
		nonlocal section_index, current_lines, current_title
		content = "\n".join(current_lines).strip()
		if content:
			sections.append({"section": _slugify(current_title), "text": content})
			section_index += 1
		current_lines = []

	for line in lines:
		if heading_pattern.match(line):
			flush()
			current_title = line.lstrip("#").strip() or f"section_{section_index}"
		else:
			current_lines.append(line)

	flush()

	if not sections:
		sections.append({"section": "section_1", "text": text.strip()})

	return sections


def _slugify(value: str) -> str:
	cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
	return cleaned or "section"


def _fallback_embed(text: str) -> List[float]:
	dim = max(int(settings.EMBEDDING_DIMENSION), 32)
	vec = [0.0] * dim
	for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()):
		digest = hashlib.sha256(token.encode("utf-8")).digest()
		idx = int.from_bytes(digest[:4], "big") % dim
		vec[idx] += 1.0
	norm = math.sqrt(sum(v * v for v in vec)) or 1.0
	return [v / norm for v in vec]
