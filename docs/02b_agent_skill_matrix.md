# Agent Capability Matrix: Skill Mapping & Container Assignment
**Version:** 1.0  
**Date:** 2026-03-14  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Status:** MVP Phase 1

---

## Overview

This document maps each of the 7 AI agents to their owned skills, callable skills, required tools, data contracts, validation rules, and container assignments. This is the bridge between high-level agent design (02_agent_design.md) and system architecture (Stage 5).

**Key Principle:** Skills owned by an agent run in its backend container. Skills callable from other agents are exposed via inter-agent APIs (PostgreSQL table for MVP, REST for Phase 2).

---

## Agent 1: Routing Agent

### 1. Agent Name & Responsibility
**Routing Agent** — Entry point and request type classifier. Analyzes incoming user requests and routes to appropriate specialist agent without processing content.

### 2. Skills Owned by This Agent
| Skill Name | Description | Purpose |
|---|---|---|
| `request_classification` | Analyze request type (upload, query, approval) | Route to correct specialist agent |
| `metadata_extraction` | Extract document type, size, user role | Route decision based on metadata only |
| `workflow_state_lookup` | Retrieve current workflow state from DB | Determine if request is resuming or new |

### 3. Skills Callable by This Agent
| Skill Name | Owned By Agent | Purpose |
|---|---|---|
| `risk_flag_check` | Validation Agent | Pre-check if high-risk content before routing |
| `user_context_retrieve` | Memory Agent | Get user preferences and past workflows |

### 4. Tools Used by Each Skill
| Skill Name | Tool(s) | Purpose |
|---|---|---|
| `request_classification` | T001 (LLM Inference) | Classify request type using LLM |
| `metadata_extraction` | T019 (Config Manager), T002 (Logger) | Extract metadata, log classification |
| `workflow_state_lookup` | T016 (PostgreSQL Client) | Query agent_state table |

### 5. Input / Output per Skill
| Skill Name | Input | Output |
|---|---|---|
| `request_classification` | `{user_input: str, document_type?: str, request_context: dict}` | `{target_agent: str, confidence: 0-1, priority: str, risk_flags: []}` |
| `metadata_extraction` | `{file: bytes, user_id: uuid, project_id: uuid}` | `{doc_type: str, doc_size_mb: float, user_role: str}` |
| `workflow_state_lookup` | `{workflow_id: uuid}` | `{workflow_state: dict, current_step: int, last_agent: str}` |

### 6. Validation / Fallback
| Skill Name | Validation Rule | Fallback Behaviour |
|---|---|---|
| `request_classification` | confidence >= 0.7; target_agent in [valid agents] | Default to Data Extraction Agent (safe path) |
| `metadata_extraction` | file_size <= 500 MB; file_type recognized | Reject upload + notify user of size/format issue |
| `workflow_state_lookup` | workflow_id exists in DB | Return empty state; treat as new workflow |

### 7. Handoff to Next Agent
| Condition | Next Agent | Data Passed |
|---|---|---|
| `request_type == "upload_audio"` | Data Extraction Agent | `{file: bytes, file_type: "audio", speakers: []}` |
| `request_type == "search"` | RAG Verification Agent | `{query: str, project_id: uuid}` |
| `request_type == "generate"` | Summarization Agent | `{extracted_data: dict, template_type: str}` |
| `content == "high_risk"` | Validation Agent | `{doc_id: uuid, risk_flags: []}` (pre-check only) |
| `user_asks_context` | Memory Agent | `{user_id: uuid, project_id: uuid, query: str}` |
| `suspicious_input_detected` | Prompt Injection Prevention Agent | `{raw_input: str, pattern_detected: str}` |

### 8. Backend Container
- **Container name:** `rag_service`
- **Responsibilities handled:** Agent instantiation, request routing, metadata parsing
- **Port:** 5002
- **Process:** Runs within FastAPI server (RAG Service)

### 9. Separate AI Service Container
- **Required:** No (for MVP)
- **Rationale:** Lightweight orchestration; no heavy LLM inference in routing logic
- **Future (Phase 2):** Could be split into separate `routing_service` if needed

### 10. External Managed Service
- **Service name:** N/A
- **All operations local to RAG Service**

---

## Agent 2: Data Extraction Agent

### 1. Agent Name & Responsibility
**Data Extraction Agent** — Parse unstructured content (transcripts, emails, documents) into structured business entities with high fidelity. Preserves original text verbatim and flags uncertainties.

### 2. Skills Owned by This Agent
| Skill Name | Description | Purpose |
|---|---|---|
| `audio_transcription` | Convert audio → transcript with speaker labels | Process meeting recordings via STT |
| `entity_extraction` | Extract decisions, action items, requirements from text | Structure unstructured content |
| `email_parsing` | Parse email threads for action items and context | Extract from email ingestion |
| `document_parsing` | Extract text from PDF/DOCX/XLSX files | Process uploaded documents |
| `ocr_text_extraction` | Extract text from images using OCR | Handle scanned documents |
| `data_validation_initial` | Validate extracted entities against schema | Ensure output quality >85% recall |

### 3. Skills Callable by This Agent
| Skill Name | Owned By Agent | Purpose |
|---|---|---|
| `rag_search_verification` | RAG Verification Agent | Cross-check extracted entities against KB |
| `user_context_retrieve` | Memory Agent | Get past extractions for consistency check |
| `confidence_score_calculation` | Validation Agent | Calculate confidence for each extraction |

### 4. Tools Used by Each Skill
| Skill Name | Tool(s) | Purpose |
|---|---|---|
| `audio_transcription` | T017 (STT Processor - ElevenLabs), T018 (STT Fallback - Deepgram) | Transcribe audio to text with diarization |
| `entity_extraction` | T001 (LLM Inference) | Extract structured entities using LLM |
| `email_parsing` | T012 (Email Reader - Gmail API), T001 (LLM) | Fetch & parse emails |
| `document_parsing` | T003 (Document Parser - PyPDF/python-docx), T006 (OCR - Tesseract) | Extract text from various formats |
| `ocr_text_extraction` | T006 (OCR Engine), T001 (LLM - post-OCR cleanup) | Recognize text from images |
| `data_validation_initial` | T004 (JSON Schema Validator), T002 (Logger) | Validate extraction schema |

### 5. Input / Output per Skill
| Skill Name | Input | Output |
|---|---|---|
| `audio_transcription` | `{audio_file: bytes, language: "zh-TW"\|"en", keyterms: [str]}` | `{transcript: str, speakers: [str], confidence: 0-1, segments: [{time, speaker, text}]}` |
| `entity_extraction` | `{transcript: str, doc_type: "meeting"\|"email"\|"document"}` | `{decisions: [{text, stakeholders, context}], action_items: [{owner, task, due_date}], requirements: [{type, description}], risks: [str]}` |
| `email_parsing` | `{email_thread: [email], sender_id: uuid, project_id: uuid}` | `{from: str, to: [str], subject: str, body: str, action_items: [], decisions: []}` |
| `document_parsing` | `{file: bytes, file_type: "pdf"\|"docx"\|"xlsx"}` | `{text: str, pages: int, sections: [str], metadata: {created_date, author}}` |
| `ocr_text_extraction` | `{image_file: bytes}` | `{text: str, confidence: 0-1, readable: bool}` |
| `data_validation_initial` | `{extracted_data: dict, schema: json_schema}` | `{valid: bool, errors: [str], warnings: [str]}` |

### 6. Validation / Fallback
| Skill Name | Validation Rule | Fallback Behaviour |
|---|---|---|
| `audio_transcription` | Confidence >= 60%; transcript length > 0 | Fallback to Deepgram; if fails, mark NEEDS_CONFIRMATION |
| `entity_extraction` | Recall >= 85%; precision >= 95% | Mark uncertain items as "NEEDS_CONFIRMATION"; do not hallucinate |
| `email_parsing` | Subject & body not empty | Skip email if parsing fails; log error |
| `document_parsing` | Text extracted >= 100 chars | Fallback to OCR if PDF text-extraction fails |
| `ocr_text_extraction` | OCR confidence >= 50% | Mark low-confidence words with *asterisks*; flag for manual review |
| `data_validation_initial` | All required fields present; no schema violations | Reject extraction; request re-run or manual input |

### 7. Handoff to Next Agent
| Condition | Next Agent | Data Passed |
|---|---|---|
| Extraction complete | RAG Verification Agent | `{extracted_entities: dict, confidence_scores: dict, marked_questions: []}` |
| High-risk entities detected | Validation Agent | `{extracted_data: dict, risk_flags: ["legal", "financial"], confidence: 0-1}` |
| User asks context during extraction | Memory Agent | `{user_id: uuid, project_id: uuid, extraction_context: dict}` |

### 8. Backend Container
- **Container name:** `rag_service`
- **Responsibilities handled:** STT orchestration, entity extraction (LLM calls), document parsing
- **Port:** 5002
- **Process:** Long-running extraction agent instance

### 9. Separate AI Service Container
- **Required (MVP):** No
- **Required (Phase 2):** Yes — LLM inference could be isolated in separate `llm_inference_service`
- **Rationale:** Separate LLM container allows model swapping, scaling, and A/B testing

### 10. External Managed Service
- **ElevenLabs Scribe v2** (STT primary)
- **Deepgram** (STT fallback)
- **Gmail API** (Email retrieval)
- **Google Drive API** (Document upload/storage)
- **OpenRouter** (LLM inference for extraction prompts)

---

## Agent 3: RAG Verification Agent

### 1. Agent Name & Responsibility
**RAG Verification Agent** — Ground all AI-generated claims in knowledge base. Search vector DB for similar past documents, cross-reference generated content, cite sources, and prevent hallucination.

### 2. Skills Owned by This Agent
| Skill Name | Description | Purpose |
|---|---|---|
| `kb_semantic_search` | Query Qdrant for similar documents using vector embeddings | Find supporting evidence from past documents |
| `claim_grounding_check` | Verify if claims are supported by KB results | Detect hallucinations and unsupported statements |
| `source_citation_generation` | Create citeable references to source documents | Track provenance for all claims |
| `result_reranking` | Re-rank search results by relevance | Improve quality of top-K results |
| `confidence_scoring_rag` | Calculate grounding confidence per claim | Provide transparency on evidence quality |

### 3. Skills Callable by This Agent
| Skill Name | Owned By Agent | Purpose |
|---|---|---|
| `text_embedding` | T010 (Text Embedder in tools matrix) | Generate embeddings for query claims |
| `relevance_scoring` | T009 (BERTScore Evaluator) | Score semantic relevance (internal tool call) |
| `user_context_retrieve` | Memory Agent | Get project context for scoped search |

### 4. Tools Used by Each Skill
| Skill Name | Tool(s) | Purpose |
|---|---|---|
| `kb_semantic_search` | T007 (Qdrant Vector Client), T010 (Text Embedder) | Search vector DB by embedding similarity |
| `claim_grounding_check` | T001 (LLM) | LLM-based grounding evaluation (secondary) |
| `source_citation_generation` | T002 (Logger), T016 (PostgreSQL) | Create citations from search results |
| `result_reranking` | T008 (Vector Reranker - cross-encoder) | Re-rank by semantic relevance |
| `confidence_scoring_rag` | T009 (BERTScore), T002 (Logger) | Score confidence (semantic_sim + content_overlap) / 2 |

### 5. Input / Output per Skill
| Skill Name | Input | Output |
|---|---|---|
| `kb_semantic_search` | `{query: str, project_id: uuid, top_k: 5}` | `{candidates: [{doc_id, section, similarity_score: 0-1, text}], search_time_ms: int}` |
| `claim_grounding_check` | `{claim: str, search_results: [docs], threshold: 0.4}` | `{is_grounded: bool, grounding_score: 0-1, supporting_doc_ids: []}` |
| `source_citation_generation` | `{claim: str, supporting_docs: [dict]}` | `{citation: str, source_links: [url], format: "markdown\|html"}` |
| `result_reranking` | `{query: str, candidates: [docs]}` | `{reranked_candidates: [docs], scores: [0-1]}` |
| `confidence_scoring_rag` | `{grounded_claims: int, total_claims: int, avg_similarity: float}` | `{overall_confidence: 0-1, interpretation: "HIGH"\|"MEDIUM"\|"LOW"}` |

### 6. Validation / Fallback
| Skill Name | Validation Rule | Fallback Behaviour |
|---|---|---|
| `kb_semantic_search` | Must return top-5 results; similarity > 0.3 | If Qdrant down, fallback to PostgreSQL keyword search |
| `claim_grounding_check` | Confidence >= 60% to mark as "grounded" | Mark as "NEEDS_CONFIRMATION" if < 60% |
| `source_citation_generation` | Citation format valid; source document exists | Omit citation if source cannot be verified |
| `result_reranking` | Reranked scores must form valid ranking | Return original ranking if reranker fails |
| `confidence_scoring_rag` | Score range 0-1; must be mathematically valid | Return 0.5 (neutral) if calculation fails |

### 7. Handoff to Next Agent
| Condition | Next Agent | Data Passed |
|---|---|---|
| Verification complete | Summarization Agent | `{verified_claims: dict, citations: [str], confidence: 0-1, ungrounded_items: []}` |
| Low confidence (< 40%) | Validation Agent | `{claim: str, confidence: 0-1, action: "FLAG_FOR_REVIEW"}` |
| User context needed | Memory Agent | `{user_id: uuid, project_id: uuid, search_context: str}` |

### 8. Backend Container
- **Container name:** `rag_service`
- **Responsibilities handled:** Vector search orchestration, embedding generation, reranking
- **Port:** 5002
- **Process:** RAG orchestration layer within FastAPI

### 9. Separate AI Service Container
- **Required (MVP):** No
- **Optional (Phase 2):** Yes — Embedding service in separate `embedding_service` if scaling needed
- **Rationale:** Embeddings are CPU-intensive; can be pre-computed and cached

### 10. External Managed Service
- **Qdrant Vector DB** (can be containerized or external)
  - MVP: Qdrant container via docker-compose
  - Phase 2: External Qdrant Cloud
- **Cross-encoder model** (embedded in rag_service for MVP)

---

## Agent 4: Summarization Agent

### 1. Agent Name & Responsibility
**Summarization Agent** — Convert extracted structured entities and verified content into polished, business-ready documents (meeting minutes, BRD/URS drafts, digests). Preserve all numbers, dates, and names verbatim.

### 2. Skills Owned by This Agent
| Skill Name | Description | Purpose |
|---|---|---|
| `meeting_minutes_generation` | Generate structured meeting minutes from transcript | Create formatted minutes from recordings |
| `brd_urs_generation` | Generate BRD/URS drafts from requirements & context | Create structured requirements documents |
| `digest_generation` | Create weekly/periodic summary reports | Generate backlog digests or progress reports |
| `document_formatting` | Apply templates and styling to generated content | Ensure consistent document format |
| `citation_integration` | Embed source citations into final document | Track provenance in output |

### 3. Skills Callable by This Agent
| Skill Name | Owned By Agent | Purpose |
|---|---|---|
| `confidence_score_calculation` | Validation Agent | Aggregate confidence for entire document |
| `user_context_retrieve` | Memory Agent | Get user style preferences, past templates |

### 4. Tools Used by Each Skill
| Skill Name | Tool(s) | Purpose |
|---|---|---|
| `meeting_minutes_generation` | T001 (LLM Inference), T011 (Markdown Formatter) | Generate minutes using LLM + template |
| `brd_urs_generation` | T001 (LLM Inference), T011 (Markdown Formatter) | Generate BRD using LLM + structured template |
| `digest_generation` | T001 (LLM), T013 (Google Sheets Client) | Aggregate data & create summary |
| `document_formatting` | T011 (Markdown Formatter), T002 (Logger) | Apply formatting & validate output |
| `citation_integration` | T002 (Logger), T016 (PostgreSQL) | Embed citations from RAG verification |

### 5. Input / Output per Skill
| Skill Name | Input | Output |
|---|---|---|
| `meeting_minutes_generation` | `{transcript: str, speakers: [str], extracted: {decisions, action_items}, citations: [str]}` | `{minutes_md: str, format_valid: bool, includes_all_sections: bool}` |
| `brd_urs_generation` | `{requirements: [dict], project_context: str, citations: [str]}` | `{brd_md: str, sections_present: [str], format_valid: bool}` |
| `digest_generation` | `{week_start: date, action_items: [dict], metrics: {completed, pending, blocked}}` | `{digest_md: str, item_count: int, generated_timestamp: datetime}` |
| `document_formatting` | `{raw_content: str, template_type: str}` | `{formatted_md: str, readability_score: 0-10}` |
| `citation_integration` | `{document: str, citations: [str]}` | `{cited_document: str, citation_count: int}` |

### 6. Validation / Fallback
| Skill Name | Validation Rule | Fallback Behaviour |
|---|---|---|
| `meeting_minutes_generation` | All required sections present; no hallucinated content | Use template-based fallback if LLM fails |
| `brd_urs_generation` | All required fields filled; format schema valid | Return skeleton template if generation fails |
| `digest_generation` | Metrics sum to total items; no negative counts | Return empty digest with count=0 |
| `document_formatting` | Markdown is valid; no syntax errors | Pass through raw content if formatting fails |
| `citation_integration` | Citations reference valid documents | Skip citations if references invalid |

### 7. Handoff to Next Agent
| Condition | Next Agent | Data Passed |
|---|---|---|
| Document generation complete | Validation Agent | `{document: str, doc_type: str, citations: [str], confidence: 0-1}` |
| User requests context during generation | Memory Agent | `{user_id: uuid, project_id: uuid, generation_context: dict}` |

### 8. Backend Container
- **Container name:** `rag_service`
- **Responsibilities handled:** Document generation orchestration, template application, formatting
- **Port:** 5002
- **Process:** Summarization agent instance

### 9. Separate AI Service Container
- **Required (MVP):** No
- **Recommended (Phase 2):** Yes — Separate `document_generation_service` for LLM inference
- **Rationale:** Isolates expensive LLM calls; enables model A/B testing

### 10. External Managed Service
- **OpenRouter / DeepSeek** (LLM for document generation)
- **Google Sheets API** (For digest data aggregation)

---

## Agent 5: Validation Agent

### 1. Agent Name & Responsibility
**Validation Agent** — Quality gate before human review. Check format compliance, flag legal/financial/high-risk items, calculate confidence scores, and apply business rules. Never approves; only flags.

### 2. Skills Owned by This Agent
| Skill Name | Description | Purpose |
|---|---|---|
| `format_compliance_check` | Verify all required document sections present | Ensure output follows template schema |
| `risk_detection` | Identify legal, financial, security terms | Flag content requiring specialized review |
| `confidence_score_aggregation` | Calculate overall confidence from extraction + verification | Provide decision support score |
| `business_rule_validation` | Apply project-specific rules (e.g., "all contracts need Legal review") | Enforce business policies |
| `redundancy_check` | Detect duplicate action items or contradictions | Identify data quality issues |

### 3. Skills Callable by This Agent
| Skill Name | Owned By Agent | Purpose |
|---|---|---|
| `hallucination_detection` | RAG Verification Agent (via confidence scoring) | Check for ungrounded claims |
| `user_context_retrieve` | Memory Agent | Get approval workflow rules for project |

### 4. Tools Used by Each Skill
| Skill Name | Tool(s) | Purpose |
|---|---|---|
| `format_compliance_check` | T004 (JSON Schema Validator), T002 (Logger) | Validate document structure |
| `risk_detection` | T005 (Regex Pattern Matcher), T001 (LLM - secondary), T024 (Audit Logger) | Detect risk keywords & patterns |
| `confidence_score_aggregation` | T002 (Logger) | Aggregate scores: 0.4*completeness + 0.4*grounding + 0.2*risk_factor |
| `business_rule_validation` | T016 (PostgreSQL Client), T002 (Logger) | Query and apply project rules |
| `redundancy_check` | T001 (LLM - semantic dedup) | Detect semantic duplicates |

### 5. Input / Output per Skill
| Skill Name | Input | Output |
|---|---|---|
| `format_compliance_check` | `{document: str, doc_type: str, schema: json_schema}` | `{compliant: bool, missing_sections: [str], errors: [str]}` |
| `risk_detection` | `{document: str, content: str}` | `{risk_flags: [{type: "legal"\|"financial"\|"security", severity, matched_text}], has_pii: bool}` |
| `confidence_score_aggregation` | `{completeness: 0-1, grounding: 0-1, risk_level: 0-1}` | `{overall_confidence: 0-1, interpretation: "VERY_HIGH"\|"HIGH"\|"MEDIUM"\|"LOW"\|"VERY_LOW"}` |
| `business_rule_validation` | `{document: dict, project_id: uuid, doc_type: str}` | `{rule_violations: [str], required_approvers: [str]}` |
| `redundancy_check` | `{action_items: [dict], requirements: [dict]}` | `{duplicates: [{item1, item2, similarity: 0-1}], deduplicated_count: int}` |

### 6. Validation / Fallback
| Skill Name | Validation Rule | Fallback Behaviour |
|---|---|---|
| `format_compliance_check` | Confidence = 100% pass/fail; no partial | Reject document if schema invalid; request reformatting |
| `risk_detection` | No false negatives on critical patterns | Accept <2% false-positive flagging rate |
| `confidence_score_aggregation` | Score must be 0-1, mathematically valid | Return 0.5 (neutral) if calculation fails |
| `business_rule_validation` | All applicable rules checked | Return empty violations if rules DB unavailable |
| `redundancy_check` | Similarity threshold >= 0.7 to flag duplicate | Skip dedup if LLM unavailable; log warning |

### 7. Handoff to Next Agent
| Condition | Next Agent | Data Passed |
|---|---|---|
| Validation passes (no critical issues) | HITL Approval | `{document: str, confidence: 0-1, risk_flags: [], ready_for_approval: true}` |
| Risk flags present | Appropriate specialist (Legal/Finance/PM) | `{document: str, risk_flags: [{type, severity, item}], action: "ESCALATE"}` |
| Low confidence (< 0.4) | Data Extraction Agent (revision) | `{document: str, issues: [str], action: "REVISION_NEEDED"}` |
| User asks context | Memory Agent | `{user_id: uuid, project_id: uuid, validation_context: dict}` |

### 8. Backend Container
- **Container name:** `rag_service`
- **Responsibilities handled:** Validation orchestration, risk detection, scoring
- **Port:** 5002
- **Process:** Validation agent instance within FastAPI

### 9. Separate AI Service Container
- **Required:** No (for MVP)
- **Optional (Phase 2):** Could be isolated if risk detection becomes compute-intensive

### 10. External Managed Service
- **PostgreSQL** (business rules storage)
- **OpenRouter / DeepSeek** (LLM risk detection - optional secondary layer)

---

## Agent 6: Memory Agent

### 1. Agent Name & Responsibility
**Memory Agent** — Maintain conversational and project-level context. Store/retrieve conversation history, user preferences, workflow state. Enable "continue from last session" and cross-agent state sharing.

### 2. Skills Owned by This Agent
| Skill Name | Description | Purpose |
|---|---|---|
| `conversation_store_short_term` | Save conversation turns to Redis | Fast access to recent context (1 hour) |
| `conversation_retrieve_short_term` | Fetch recent conversation from Redis | Provide context for current turn |
| `conversation_store_long_term` | Archive conversation to PostgreSQL | Permanent audit trail (12 months) |
| `conversation_retrieve_long_term` | Fetch historical context from PostgreSQL | Support "context from past week" queries |
| `workflow_state_store` | Save shared workflow state to agent_state table | Enable multi-agent coordination |
| `workflow_state_retrieve` | Retrieve shared state during handoffs | Provide context to next agent |
| `user_preferences_store` | Save user language, approval thresholds | Personalize system behaviour |
| `user_preferences_retrieve` | Fetch user preferences | Apply personalization to outputs |

### 3. Skills Callable by This Agent
| Skill Name | Owned By Agent | Purpose |
|---|---|---|
| `pii_masking` | (Built-in, see tools) | Mask sensitive data on retrieval |
| `audit_logging` | (Audit logger tool) | Log all memory access for compliance |

### 4. Tools Used by Each Skill
| Skill Name | Tool(s) | Purpose |
|---|---|---|
| `conversation_store_short_term` | T015 (Redis Client) | Write conversation turns to Redis |
| `conversation_retrieve_short_term` | T015 (Redis Client) | Query Redis for recent turns |
| `conversation_store_long_term` | T016 (PostgreSQL Client) | Insert conversation_history rows |
| `conversation_retrieve_long_term` | T016 (PostgreSQL Client) | Query PostgreSQL with date filters |
| `workflow_state_store` | T016 (PostgreSQL Client) | Write to agent_state table |
| `workflow_state_retrieve` | T016 (PostgreSQL Client) | Read from agent_state table |
| `user_preferences_store` | T016 (PostgreSQL Client) | Write to users table preferences column |
| `user_preferences_retrieve` | T016 (PostgreSQL Client) | Query users table |

### 5. Input / Output per Skill
| Skill Name | Input | Output |
|---|---|---|
| `conversation_store_short_term` | `{user_id: uuid, project_id: uuid, turn: {timestamp, user_msg, agent_response}}` | `{stored: bool, ttl_seconds: 3600}` |
| `conversation_retrieve_short_term` | `{user_id: uuid, project_id: uuid, max_turns: 10}` | `{turns: [dict], retrieved_from: "redis"}` |
| `conversation_store_long_term` | `{user_id: uuid, project_id: uuid, turn: {timestamp, user_msg, agent_response, context}}` | `{stored: bool, row_id: int}` |
| `conversation_retrieve_long_term` | `{user_id: uuid, project_id: uuid, start_date: date, end_date: date}` | `{turns: [dict], retrieved_from: "postgresql"}` |
| `workflow_state_store` | `{workflow_id: uuid, project_id: uuid, state_data: dict, expires_at: datetime}` | `{stored: bool, expires_at: datetime}` |
| `workflow_state_retrieve` | `{workflow_id: uuid, agent_name: str}` | `{state_data: dict, last_updated: datetime, agent: str}` |
| `user_preferences_store` | `{user_id: uuid, preferences: {language: str, approval_threshold: 0-1}}` | `{stored: bool}` |
| `user_preferences_retrieve` | `{user_id: uuid}` | `{preferences: {language, threshold, timezone}, pii_masked: bool}` |

### 6. Validation / Fallback
| Skill Name | Validation Rule | Fallback Behaviour |
|---|---|---|
| `conversation_store_short_term` | Redis connection healthy; TTL = 1 hour | Fall through to PostgreSQL if Redis down |
| `conversation_retrieve_short_term` | Retrieval latency < 50ms | Fallback to PostgreSQL if Redis unavailable |
| `conversation_store_long_term` | PostgreSQL write successful; no duplicates | Log error and retry; do not lose data |
| `conversation_retrieve_long_term` | Query completes in < 1 second | Return partial results if query times out |
| `workflow_state_store` | State serializes to JSON; expires_at valid | Reject if state too large (> 1MB) |
| `workflow_state_retrieve` | agent_state row exists; not expired | Return empty state if row missing |
| `user_preferences_store` | User exists; preferences schema valid | Create default preferences if missing |
| `user_preferences_retrieve` | Apply PII masking on retrieval if user_role NOT in [Legal, Admin] | Return masked version for non-privileged users |

### 7. Handoff to Next Agent
**Memory Agent does not typically hand off.** Instead, it provides context **to** all other agents on demand.

| Request Source | Use Case | Data Retrieved |
|---|---|---|
| Any agent, any time | "Get context for this workflow" | `{workflow_state: dict, user_preferences: dict, recent_history: []}` |
| User session start | "Resume from last session" | `{recent_turns: [last 5 turns], workflow_id: uuid}` |
| Validation Agent | "Get approval rules for this project" | `{project_config: {workflow_approvers}, user_roles: dict}` |

### 8. Backend Container
- **Container name:** `rag_service`
- **Responsibilities handled:** Memory orchestration, Redis/PostgreSQL client management
- **Port:** 5002
- **Process:** Memory agent instance

### 9. Separate AI Service Container
- **Required:** No — Memory Agent is data broker, not AI agent
- **Rationale:** No LLM inference; pure data operations

### 10. External Managed Service
- **Redis** (short-term memory cache)
  - MVP: docker-compose redis service
  - Phase 2: Managed Redis (AWS ElastiCache, Redis Cloud)
- **PostgreSQL** (long-term memory)
  - MVP: docker-compose postgres service
  - Phase 2: Managed PostgreSQL (AWS RDS, Railway PostgreSQL)

---

## Agent 7: Prompt Injection Prevention Agent

### 1. Agent Name & Responsibility
**Prompt Injection Prevention Agent** — Security gate for all user inputs. Detect and block adversarial patterns (prompt injection, SQL injection, jailbreak attempts). Transparent blocking with feedback to user.

### 2. Skills Owned by This Agent
| Skill Name | Description | Purpose |
|---|---|---|
| `pattern_matching_injection` | Detect known injection patterns via regex | Block SQL, prompt, code injection attempts |
| `llm_based_detection` | Secondary LLM-based anomaly detection | Catch novel or sophisticated attacks |
| `security_logging` | Log all blocked inputs for audit trail | Track security events for compliance |
| `user_feedback_generation` | Create transparent feedback on why blocked | Help users understand security policies |

### 3. Skills Callable by This Agent
| Skill Name | Owned By Agent | Purpose |
|---|---|---|
| (None — operates independently at entry point) | N/A | Runs before downstream agents |

### 4. Tools Used by Each Skill
| Skill Name | Tool(s) | Purpose |
|---|---|---|
| `pattern_matching_injection` | T005 (Regex Pattern Matcher), T002 (Logger) | Fast pattern detection |
| `llm_based_detection` | T001 (LLM Inference) | Semantic anomaly detection (optional, high-confidence only) |
| `security_logging` | T024 (Audit Logger), T020 (Error Tracker) | Log security events |
| `user_feedback_generation` | T002 (Logger) | Generate user-facing feedback |

### 5. Input / Output per Skill
| Skill Name | Input | Output |
|---|---|---|
| `pattern_matching_injection` | `{user_input: str}` | `{is_injection: bool, pattern_type?: str, confidence: 0.95}` |
| `llm_based_detection` | `{user_input: str, context?: str}` | `{is_injection: bool, confidence: 0-1, reasoning: str}` |
| `security_logging` | `{event: str, user_id: uuid, input_hash: str, severity: str}` | `{logged: bool, log_id: uuid}` |
| `user_feedback_generation` | `{attack_type: str, user_input_preview: str}` | `{message: str, format: "text\|markdown"}` |

### 6. Validation / Fallback
| Skill Name | Validation Rule | Fallback Behaviour |
|---|---|---|
| `pattern_matching_injection` | 100% detection on known patterns; allow < 2% false positives | Block on high-confidence; warn on medium |
| `llm_based_detection` | Use only if pattern-based uncertain; confidence > 0.8 | Skip secondary check if LLM unavailable |
| `security_logging` | All blocks must be logged; never lose security events | Queue logs if audit DB temporarily down |
| `user_feedback_generation` | Message must be clear & actionable | Return generic message if specific type unknown |

### 7. Handoff to Next Agent
| Condition | Next Agent | Data Passed |
|---|---|---|
| Input passes security gate | Routing Agent | `{user_input: str, security_passed: true}` |
| Injection blocked | (Stop here) | `{error_msg: str, status: 403_FORBIDDEN}` |

### 8. Backend Container
- **Container name:** `api_service` (or `gateway`)
- **Responsibilities handled:** Security gate before all downstream processing
- **Port:** 5000 (Backend API) or 80/443 (Gateway)
- **Process:** Middleware layer — runs on **every** incoming request

### 9. Separate AI Service Container
- **Required:** No (for MVP)
- **Optional (Phase 2):** Could be edge service if attack detection becomes compute-heavy

### 10. External Managed Service
- **OpenRouter / DeepSeek** (LLM for secondary detection - optional, high-confidence only)

---

## Container Assignment Summary 🐳

### MVP Phase 1 Deployment

| Agent(s) | Backend Container | Container Name | Port | Responsibilities |
|----------|---|---|---|---|
| Routing, Data Extraction, RAG Verification, Summarization, Validation, Memory | rag_service | `rag_service` | 5002 | Core AI orchestration, all 6 agents |
| Prompt Injection Prevention | api_service | `api_service` | 5000 | Security gate (middleware) |

### Supporting Containers (Not Agents, Required for Operation)

| Component | Container Name | Port | Purpose | Image |
|---|---|---|---|---|
| API Gateway | gateway | 80/443 | Route external traffic | nginx:latest |
| PostgreSQL | postgres | 5432 | Conversation history, workflow state, audit logs | postgres:15-alpine |
| Qdrant Vector DB | qdrant | 6333 | RAG knowledge base | qdrant/qdrant:latest |
| Redis | redis | 6379 | Short-term memory (sessions, context) | redis:7-alpine |

### External Managed Services (No Container)

| Service | Provider | Purpose | Integration |
|---|---|---|---|
| ElevenLabs Scribe v2 | ElevenLabs | Audio → Transcript (STT) | API |
| Deepgram | Deepgram | Fallback STT | API |
| OpenRouter | OpenRouter | LLM inference | API |
| DeepSeek | OpenAI API / DeepSeek | LLM fallback + Chinese | API |
| Gmail API | Google | Email ingestion | OAuth2 |
| Google Drive API | Google | Document storage | OAuth2 |
| Google Sheets API | Google | Backlog data | OAuth2 |
| Telegram Bot | Telegram | Notifications | Bot API |

---

## Phase 2 Extensions (Future Containerization)

### New Agents (Not in MVP)
- **Contract Analysis Agent** — Extract clauses, risk-flag contracts
- **Cost Analysis Agent** — Identify financial figures, flag budget impacts
- **Translation Agent** — Chinese ↔ English bidirectional

### New Service Containers
- `llm_inference_service` (separate LLM server, Port 5003)
- `embedding_service` (pre-compute & cache embeddings, Port 5004)
- `document_generation_service` (dedicated summarization service, Port 5005)
- `translation_service` (dedicated translation engine, Port 5006)

---

## Skill Matrix Validation Checklist

- [x] All 7 agents have complete skill definitions
- [x] Skills owned vs skills callable clearly distinguished per agent
- [x] Every skill has input/output schema defined
- [x] Validation rules and fallback behaviour defined for every skill
- [x] Handoff conditions and data passed explicitly specified
- [x] Each agent classified into backend container / AI container / external service
- [x] 24 tools inventory mapped to agents and skills
- [x] MVP container strategy defined (single rag_service + api_service + supporting DBs)
- [x] Phase 2 scaling path clear (separate service containers for LLM, embeddings, etc.)
- [x] External managed services identified (ElevenLabs, OpenRouter, Google APIs, Telegram)

---

**End of Agent Capability Matrix**
