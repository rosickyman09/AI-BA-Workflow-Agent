---
name: stage7f-rag-knowledge-base
description: Implements the RAG knowledge base with document embedding, semantic search, Qdrant vector storage, and source citation. Use this skill when the user wants to build the RAG pipeline, embed documents into a vector store, implement semantic search with cosine similarity, add re-ranking, filter search results by project scope, add source citations, or meet performance targets for search latency. Trigger when the user mentions "RAG", "vector store", "Qdrant", "embedding", "semantic search", "cosine similarity", "re-ranking", "citations", "knowledge base", "sentence-transformers", or wants to implement Stage 7F after the AI agent pipeline is working.
---

## Stage 7F — Agent Mode: RAG Knowledge Base Module

### Purpose
Build the complete RAG (Retrieval-Augmented Generation) knowledge base: embed documents using sentence-transformers, store vectors in Qdrant with project-scoped isolation, implement semantic search with cosine similarity and re-ranking, and generate source citations in `[doc_id#section]` format.

> ⚠️ Performance target: search response < 500ms, confidence threshold >= 0.6. Do NOT change architecture or docker-compose.yml.

---

### Prerequisites

- [ ] Stage 7E complete — AI agent pipeline working
- [ ] `docs/02_agent_design.md` exists (RAG pipeline design)
- [ ] `rag_service/app/main.py` exists
- [ ] Qdrant vector store running (port 6333)
- [ ] sentence-transformers available in requirements.txt

---

### Step 1 — Switch to Agent Mode and Attach Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach both input files:
   ```
   docs/02_agent_design.md
   rag_service/app/main.py
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Agent Mode):

```
Implement the RAG Knowledge Base in rag_service.

Task 1 — Document Embedding Pipeline:
- Use sentence-transformers for embedding
  (model: all-MiniLM-L6-v2 or equivalent)
- Implement section-aware chunking:
  chunk_size=512 tokens, overlap=50 tokens
- Store embeddings to Qdrant:
  - Collection per project (project_id scoped)
  - Payload: {doc_id, section, text, page, source}
- Endpoint: POST /rag/embed
  Input: {document_id, project_id, text_content}

Task 2 — Semantic Search:
- Cosine similarity search in Qdrant
- Top-K results (default K=5)
- Re-ranking by relevance score
- Filter by project_id (no cross-project leakage)
- Endpoint: POST /rag/search
  Input: {query, project_id, top_k?}
  Output: {results: [{text, score, citation}]}

Task 3 — Source Citation:
- Format: [doc_id#section]
- Include in every search result
- Link back to original document

Performance targets:
- Search response < 500ms
- Minimum confidence threshold: 0.6
  (filter out results below threshold)

Do NOT change architecture or docker-compose.yml.

Create:
- rag_service/app/services/vector_store.py
- rag_service/app/services/embedding.py
- rag_service/app/services/search.py
```

---

### Step 3 — Expected Output Files

```
rag_service/app/services/
├── vector_store.py             ← Qdrant client, collection management
├── embedding.py                ← sentence-transformers embedding pipeline
└── search.py                   ← Semantic search + re-ranking + citation
```

---

### Step 4 — Qdrant Collection Design

| Field | Value |
|---|---|
| Collection naming | `project_{project_id}` |
| Vector size | 384 (all-MiniLM-L6-v2) |
| Distance metric | Cosine |
| Payload fields | doc_id, section, text, page, source, created_at |

---

### Step 5 — Acceptance Tests (Must All Pass)

#### Test 1 — Embed a Document
```powershell
$token = "your_access_token"
$body = '{
  "document_id": "test-doc-id",
  "project_id": "660e8400-...",
  "text_content": "The meeting discussed requirements for user authentication..."
}'
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5002/rag/embed" `
  -Headers @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" } `
  -Body $body
# Expected: { status: "embedded", chunks: N }
```

#### Test 2 — Search Returns Results
```powershell
$body = '{
  "query": "authentication requirements",
  "project_id": "660e8400-...",
  "top_k": 5
}'
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5002/rag/search" `
  -Headers @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" } `
  -Body $body
# Expected: { results: [...] } with citations ✅
```

#### Test 3 — Citations Present
- Every result contains `citation` in format `[doc_id#section]` ✅

#### Test 4 — Performance
- Measure search response time → must be < 500ms ✅

#### Test 5 — Project Isolation
- Search with project A's token → should NOT return project B's documents ✅

---

### Output

```
rag_service/app/services/vector_store.py   ← Qdrant operations
rag_service/app/services/embedding.py      ← Embedding pipeline
rag_service/app/services/search.py         ← Search + re-rank + cite
```

---

### Checklist

- [ ] Agent Mode activated before submitting prompt
- [ ] Both input files attached
- [ ] `POST /rag/embed` endpoint created
- [ ] sentence-transformers embedding working
- [ ] Section-aware chunking implemented (512 tokens, 50 overlap)
- [ ] Qdrant collections scoped per project_id
- [ ] `POST /rag/search` endpoint created
- [ ] Cosine similarity search working
- [ ] Top-K results with re-ranking
- [ ] project_id filter applied (no cross-project results)
- [ ] Source citations in `[doc_id#section]` format
- [ ] Results below 0.6 confidence filtered out
- [ ] Search response < 500ms (tested)
- [ ] All 5 acceptance tests pass
- [ ] 🔒 All tests pass before proceeding to Stage 7G
