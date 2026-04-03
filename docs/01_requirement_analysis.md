# Requirement Analysis: AI BA Agent
**Version:** 1.0  
**Date:** 2026-03-14  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Status:** MVP Phase 1

---

## 1. Business Goal

### Core Objective
Automate the transformation of meeting recordings, emails, and documents into structured business artifacts to reduce BA document preparation and follow-up communication time.

### Key Outcomes
- Reduce document preparation time for BA team
- Standardize meeting minutes, requirements, and contract documentation
- Enable searchable knowledge base for project-scoped intelligence
- Improve document version control and approval workflows
- Support role-based access and compliance requirements

### Success Metrics
- Meeting minutes generated within 2 minutes of recording completion
- BRD/URS draft accuracy >90% (measured by approver feedback)
- Knowledge base hit rate >70% for chatbot queries
- Backlog follow-up completion rate >95% via Telegram notifications
- Human-in-loop approval turn-around time <1 business day

---

## 2. Functional Modules

### 2.1 Document Ingestion & STT Processing
**Purpose:** Accept multiple input formats and convert to transcribed text

**Inputs:**
- Meeting recordings (audio files)
- Email threads (via Gmail API integration)
- Documents (PDF, Word, Excel)

**Processing:**
- ElevenLabs Scribe v2 API for STT transcription
- Speaker Diarization (auto-identify speakers)
- Keyterm Prompting (enhance business terminology accuracy)
- Webhook callback to n8n for async processing

**Outputs:**
- Transcribed text with speaker labels
- Processing status updates to user
- Storage reference in Google Drive

**APIs & Dependencies:**
- ElevenLabs Scribe v2 (STT)
- Deepgram (backup STT)
- Gmail API (email ingestion)

---

### 2.2 Automatic Document Generation
**Purpose:** Generate structured business documents from processed content

**Generated Artifacts:**
1. **Structured Meeting Minutes**
   - Attendees & speakers identified
   - Key decisions extracted
   - Action items with ownership
   - Timeline markers

2. **Business Requirements (BRD/URS) Drafts**
   - Functional requirements extracted
   - Non-functional requirements identified
   - Story cards or use case format
   - Risk flags for legal/financial terms

3. **Contract & Terms Initial Drafts** (Phase 2)
   - Clause extraction
   - Risk flagging
   - Suggested modifications

**Processing Logic:**
- Data Extraction Agent: Parse transcript for entities, decisions, requirements
- Summarization Agent: Condense into structured formats
- RAG Verification Agent: Cross-reference with past documents
- Validation Agent: Quality gate & risk flagging

**Outputs:**
- Draft documents with source citations
- Confidence scores per section
- Flagged high-risk items for human review

---

### 2.3 Version Control & Approval Workflow
**Purpose:** Track document changes and manage multi-step approvals

**Features:**
- Document versioning with immutable audit trail
- Configurable approval workflows (e.g., BA → PM → Business Owner → Legal)
- Approval status tracking by workflow step
- Complete audit logging (who, what, when, why)

**Approval Roles:**
- Admin: Full access, user management
- BA / PM / Tech Lead: Standard users, can create/edit within project
- Business Owner / Legal: Approval authority, view-only of non-owned projects
- IT: Read-only across all projects

**Workflows:**
- Version 1: Draft → BA Review → Approval Submission → Multi-level Approval → Published
- Version 2: Rejected → BA Edit → Re-submit

**Data Tracked:**
- Version number & timestamp
- Author & content hash
- Reviewer & decision
- Comments & rejection reasons

---

### 2.4 RAG Knowledge Base
**Purpose:** Index documents and enable intelligent search with source citations

**Features:**
- Project-scoped vector embeddings
- Semantic search across all indexed documents
- Source citation (document ID + section reference)
- Chatbot interface (web + Telegram)

**Knowledge Sources:**
- Processed documents (meeting minutes, BRDs, etc.)
- User documents (uploaded files)
- Google Drive documents

**Search Capabilities:**
- Semantic search: "Find similar requirements from past projects"
- Entity search: "Requirements related to Payment Module"
- Trend search: "All contractual risks from Q2"

**Implementation:**
- Vector DB: Qdrant (project-scoped collections)
- Embedding model: OpenRouter + DeepSeek LLM
- Language support: Traditional Chinese + English

---

### 2.5 Backlog & Follow-up Management
**Purpose:** Auto-track action items and send notifications

**Triggers & Workflows:**
1. **Daily Backlog Scan (Cron)**
   - Time: 8 AM daily
   - Action: Scan Google Sheets for status=Blocked/Overdue/Waiting Approval
   - Notification: Telegram to owner with status & due date

2. **Weekly Digest Report**
   - Time: Friday 5 PM
   - Content: Summary of all action items, completed/pending/blocked
   - Distribution: Telegram broadcast or email

3. **Approval Reminders**
   - Trigger: Document pending approval >2 days
   - Action: Reminder to assigned approver
   - Channel: Telegram / Email

**Data Source:**
- Google Sheets (backlog tracking, managed by BA)
- PostgreSQL (document approval status)

**Status Values:**
- New / In Progress / Blocked / Overdue / Waiting Approval / Completed

---

### 2.6 Human-in-the-Loop (HITL) Confirmation
**Purpose:** Enforce manual review for high-risk content

**Trigger Points:**
- All legal/contractual terms flagged automatically
- All financial figures (cost, budget, pricing) flagged
- High-risk business decisions identified by validation agent
- Sensitivity labels (PII, confidential, etc.)

**Approval Process:**
1. AI system detects high-risk item
2. Flags item with reasoning & confidence score
3. Routes to designated approver (e.g., Legal for contracts)
4. Approver reviews & either:
   - Approves (document progresses)
   - Rejects with feedback (document reverts to draft)
5. All decisions logged in audit trail

**SLA Target:**
- HITL review request → approval within 24 hours (business days)

---

## 3. Non-Functional Requirements

### 3.1 Performance
| Metric | Target | Notes |
|--------|--------|-------|
| STT processing time | <5 min for 1-hour recording | Depends on ElevenLabs API |
| Document generation | <2 min | From transcript to draft |
| RAG search latency | <500 ms | Semantic search response |
| Page load time | <2 sec | Web UI responsiveness |
| Concurrent users | 20-50 | Internal team only |
| Document size limit | 500 MB | Per upload |

### 3.2 Reliability & Availability
| Aspect | Requirement |
|--------|-------------|
| Uptime target | 95% (business hours) |
| Data backup | Daily automated backups |
| Failover | Manual failover to last healthy state |
| Database redundancy | Read replicas (Phase 2) |
| API timeout handling | Retry with exponential backoff |

### 3.3 Security
| Aspect | Requirement |
|--------|-------------|
| Authentication | JWT tokens, 1-hour expiry |
| Authorization | Role-based access control (RBAC) per project |
| Data encryption | TLS/HTTPS in transit, encrypted storage for sensitive fields |
| PII handling | Auto-mask phone, SSN, email (configurable per role) |
| Audit logging | All API calls logged with user, timestamp, action |
| Log retention | 12 months minimum |
| Secrets management | Environment variables, Railway secrets manager |

### 3.4 Scalability
| Component | Approach |
|-----------|----------|
| Horizontal scaling | Each service runs in independent container |
| Load balancing | Nginx gateway distributes requests |
| Database scaling | PostgreSQL read replicas (Phase 2) |
| Vector DB scaling | Qdrant clustering for HA (Phase 2) |
| Session management | Redis cache for distributed sessions |

### 3.5 Maintainability
- Code standards: Clean code, modular functions, documented APIs
- Logging: Structured JSON logs, centralized log collection (Phase 2)
- Monitoring: Health checks, service-level metrics
- Documentation: API specs, deployment guides, runbooks
- Versioning: Semantic versioning for services & APIs

---

## 4. Data Requirements

### 4.1 Core Data Entities

**Users**
```
- user_id (PK)
- email
- role (Admin, BA, Owner, Legal, IT)
- projects (many-to-many)
- created_at, updated_at
```

**Projects**
```
- project_id (PK)
- name
- owner_id (FK: users)
- created_at, access_level
- config (approval workflow steps, retention policy)
```

**Documents**
```
- doc_id (PK)
- project_id (FK)
- title, type (meeting_minutes, brd_urs, contract)
- upload_time, status (draft, pending_approval, approved, published)
- content_hash
- google_drive_link
```

**Document Versions**
```
- version_id (PK)
- doc_id (FK)
- version_number
- content_hash
- created_by (FK: users)
- approval_status (pending, approved, rejected)
```

**Approval Workflows**
```
- workflow_id (PK)
- doc_id (FK)
- current_step
- approvers (list of user_ids per step)
- status (in_progress, approved, rejected)
- decisions (timestamp, approver, decision, comments)
```

**Audit Logs**
```
- log_id (PK)
- action (create, update, approve, publish)
- user_id (FK)
- doc_id (FK)
- timestamp
- details (JSON: before/after values)
```

**RAG Knowledge Base**
```
- Vector DB (Qdrant)
- Collections: documents_embeddings
  - document_id (PK)
  - project_id (partition key)
  - title, content_vector
  - metadata (created_date, author, status)
```

### 4.2 Data Storage Strategy

| Data Type | Storage | Backup | Notes |
|-----------|---------|--------|-------|
| Transactional | PostgreSQL | Daily snapshots | Users, projects, approvals, audit logs |
| Vector embeddings | Qdrant | Daily snapshots | RAG knowledge base |
| Documents (unparsed) | Google Drive | Built-in versioning | Original uploaded files |
| Session data | Redis | N/A | Volatile, TTL=1 hour |
| Configuration | PostgreSQL | Daily | Approval workflows, retention policies |

### 4.3 Data Retention Policy
- Audit logs: 12 months (regulatory requirement)
- Document versions: Full history (compliance)
- Session data: 1 hour (auto-purge)
- Backup copies: Latest 30 days
- Deleted projects: Soft-delete, archived for 90 days

### 4.4 PII & Data Protection
**Sensitive Fields:**
- Phone numbers → masked ****-****-****
- Email addresses → visible to approvers only
- Financial figures → masked unless user role=Legal or Admin
- SSN/ID numbers → masked ****-****-XXXX

**Access Control:**
- PII visible only to assigned reviewer
- Cross-project data isolated by project_id
- Read-only users cannot access PII
- All access logged for audit

---

## 5. AI Capabilities Required

### 5.1 AI Orchestration Framework
**Selected:** CrewAI
- Rationale: Clear role division, team task focus, state management
- Alternative: LangChain (if simpler agent composition needed)

### 5.2 Core AI Agents (7 Required)

#### 1. Routing Agent
- **Role:** Entry point, request classifier
- **Inputs:** User query, document type, workflow state
- **Outputs:** Route decision to specialized agent
- **Constraints:** No content processing, metadata-only decisions

#### 2. Data Extraction Agent
- **Role:** Parse unstructured content → structured data
- **Tasks:**
  - Extract action items with owners & deadlines
  - Identify decisions and stakeholders
  - Parse requirements from transcripts
  - Extract clauses from contracts
- **Constraints:** Preserve original text verbatim, flag gaps as "NEEDS_CONFIRMATION"

#### 3. Summarization Agent
- **Role:** Condense content while preserving critical info
- **Tasks:**
  - Generate executive summaries
  - Create meeting minutes from transcripts
  - Weekly digest from action items
  - BRD/URS drafts from raw requirements
- **Constraints:** Keep all numbers/dates/names, tag high-risk items

#### 4. RAG Verification Agent
- **Role:** Ground AI responses in knowledge base
- **Tasks:**
  - Search vector DB for similar documents
  - Cross-reference generated content
  - Identify insufficient data gaps
  - Cite sources for all claims
- **Constraints:** Project-scoped search, <60% confidence → "NEEDS_CONFIRMATION"

#### 5. Validation Agent
- **Role:** Quality gate before human review
- **Tasks:**
  - Check output format compliance
  - Flag legal/financial/high-risk items
  - Generate confidence scores
  - Apply business rules (e.g., all contracts need Legal review)
- **Constraints:** No approval authority, only flagging

#### 6. Memory Agent
- **Role:** Maintain conversational context
- **Tasks:**
  - Store user & project conversation history
  - Retrieve past decisions & context
  - Support "continue from last session"
  - Maintain user preferences (language, thresholds)
- **Constraints:** Project-scoped isolation, respect RBAC

#### 7. Prompt Injection Prevention Agent
- **Role:** Security gate for user inputs
- **Tasks:**
  - Detect adversarial patterns
  - Block prompt injection attempts
  - Log security events
- **Constraints:** Transparent blocking with feedback

### 5.3 System Skills (12 Required)

| Skill | Purpose | Implementation |
|-------|---------|-----------------|
| Document Processing | PDF/Word/Excel parsing | PyPDF, python-docx, openpyxl |
| OCR | Extract text from images | Tesseract + Python OCR wrapper |
| Knowledge Base Search | RAG semantic search | Qdrant client library |
| Summarization | Long-form condensing | LLM prompt engineering |
| Translation | Chinese ↔ English | DeepSeek LLM or translation API |
| Email Automation | Send/receive via Gmail | Gmail API client |
| File Management | Organize & classify files | Google Drive API, local filesystem |
| External API Integration | Connect to 3rd party APIs | aiohttp, requests, httpx |
| Notification | Send via Email/Telegram/Slack | Telegram Bot API, SMTP, Slack SDK |
| Workflow Decision | Conditional routing | Boolean logic + database queries |

### 5.4 LLM Model Configuration

**Primary Model:** OpenRouter
- Access: Single API endpoint to multiple models
- Models: GPT-4 (quality), DeepSeek (cost), Claude (context)
- Rationale: Flexibility, cost optimization, fallback support

**Fallback Model:** DeepSeek
- Rationale: Strong Chinese language support, cost-effective
- Use case: When OpenRouter unavailable or Chinese-heavy tasks

**Token Budget:**
- Soft limit: 100k tokens/day per project
- Hard monitoring: Log daily usage, alert if >100k
- Optimization: Summarize long contexts, use cheaper models for simple tasks

---

## 6. Risks, Assumptions & Dependencies

### 6.1 Key Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **STT Accuracy** | BRD/URS quality depends on transcript accuracy | Implement human review threshold, speaker labels, keyterm prompting |
| **LLM Hallucination** | AI might generate false information | RAG Verification Agent enforces source grounding, "[NEEDS_CONFIRMATION]" for gaps |
| **API Rate Limits** | ElevenLabs, OpenRouter may throttle | Implement queue, exponential backoff, fallback STT (Deepgram) |
| **Data Privacy Breach** | Sensitive content exposure | Encryption, RBAC, audit logging, PII masking |
| **Approval Bottleneck** | HITL slows workflow if reviewers cannot keep up | SLA monitoring, escalation alerts, async notifications |
| **Integration Complexity** | Multiple external APIs (Gmail, Google Drive, Telegram, etc.) | Webhook pattern, async processing, staging environment |
| **Scope Creep** | Phase 2 features (contracts, cost analysis) delay MVP | Clear phase gate, weekly scope review |

### 6.2 Key Assumptions

| Assumption | Validation Method |
|-----------|-------------------|
| Users have Google account for Drive/Gmail/Sheets | Confirmed in kickoff |
| Internal use only (no multi-tenant) | Confirmed in requirements |
| ElevenLabs Scribe v2 availability (SLA 99.5%) | Check SLA terms |
| Average recording length <2 hours | Business constraint |
| Approval team responds within 24 hours | Define SLA at project start |
| DocuSignature not required (manual PDF workflow) | Confirm with Legal |
| Knowledge base search accuracy acceptable at 70% | Define acceptance criteria |

### 6.3 Key Dependencies

| Dependency | Type | Risk | Mitigation |
|------------|------|------|-----------|
| ElevenLabs Scribe v2 API | External service | Service downtime | Implement fallback to Deepgram |
| OpenRouter / DeepSeek API | External service | Rate limits, downtime | Implement queue, fallback selection |
| Google APIs (Drive, Gmail, Sheets) | External service | Auth or API changes | Version pinning, test suite |
| PostgreSQL | Database | Data loss | Daily automated backups |
| Qdrant Vector DB | Database | Query failures | Health checks, fallback to keyword search |
| Railway Platform | Infrastructure | Downtime | Manual rollback procedure |
| n8n Workflow Engine | Automation | Webhook failures | Retry logic, dead-letter queue |

---

## 7. Deployment & Containerization Assumptions

### 7.1 Containerization Strategy

**Services to Containerize:**
- ✅ Frontend (React/Next.js → Nginx static)
- ✅ Backend API (Python FastAPI)
- ✅ Auth Service (Python FastAPI + JWT)
- ✅ RAG Service (Python FastAPI + LangChain)
- ✅ Gateway (Nginx reverse proxy)
- ✅ PostgreSQL (official image)
- ✅ Qdrant (official image)
- ✅ Redis (optional, official image)

**Services NOT Containerized (External):**
- n8n (use SaaS n8n.io or deploy separately)
- ElevenLabs (external API)
- OpenRouter / DeepSeek (external API)
- Google APIs (external)
- Telegram Bot (external)

### 7.2 Docker Compose Orchestration

**File Location:** `/infra/docker-compose.yml`

**Key Features:**
- Multi-container orchestration
- Service-to-service communication via Docker network
- Health checks on critical services
- Volume mounts for data persistence
- Environment variable configuration
- Multi-stage builds for optimized images

**Deployment Sequence:**
1. Database Layer (PostgreSQL → Qdrant → Redis)
2. Backend Services (Auth → API → RAG)
3. n8n Workflow Engine (if self-hosted)
4. Frontend (React build → Nginx)
5. Gateway (Route all traffic after services healthy)

### 7.3 Port Allocation (Multi-Port Architecture)

| Service | Container | Host | Purpose |
|---------|-----------|------|---------|
| Gateway | 80/443 | 80/443 | Public HTTPS entry |
| Frontend | 3000 | 3000 | Dev only |
| Backend API | 5000 | 5000 | Internal + Dev |
| Auth Service | 5001 | 5001 | Internal + Dev |
| RAG Service | 5002 | 5002 | Internal + Dev |
| PostgreSQL | 5432 | 5432 | Internal only |
| Qdrant | 6333 | 6333 | Internal + Dev |
| Redis | 6379 | 6379 | Internal only |
| n8n | 5678 | 5678 | Workflow UI + webhooks |

**Justification for Multi-Port:**
- Services independent & easier to debug
- Simpler local development (run services individually)
- Clearer service boundaries for future scaling
- Gateway provides single public entry point (80/443)

### 7.4 Environment Configuration

**Files:**
- `/infra/.env.example` (committed, for reference)
- `/infra/.env` (not committed, local secrets)

**Critical Variables:**
```
DB_PASSWORD=*** (strong, min 20 chars)
JWT_SECRET=*** (min 32 chars)
OPENROUTER_API_KEY=***
DEEPSEEK_API_KEY=***
ELEVENLABS_API_KEY=***
QDRANT_API_KEY=***
TELEGRAM_BOT_TOKEN=***
GOOGLE_*_CREDENTIALS=*** (JSON service accounts)
```

### 7.5 Dependency Version Management

**Locking Strategy:**
- Python: `==` pin all versions (requirements.txt)
- Node.js: Remove `^` and `~`, use exact versions (package.json)
- Docker base images: Pin specific version (e.g., `python:3.11-slim`, not `latest`)
- Validation: `pip check` for Python, `npm audit` for Node.js post-build

**Dependency Files (Recommended):**
- `requirements.txt` (prod dependencies)
- `requirements-dev.txt` (dev-only dependencies)
- `docs/08_dependency_versions.md` (version justifications)

### 7.6 Deployment Platforms

**Selected:** Railway (MVP Phase 1)
- Rationale: Simple, fast deployment, free tier, auto-TLS, GitHub integration
- Alternative: AWS/Azure for Phase 2 (enterprise scale)

**Deployment Sequence (Railway):**
1. Create Railway project
2. Connect GitHub repo (auto-detects docker-compose.yml)
3. Deploy database (PostgreSQL)
4. Run migrations
5. Deploy backend services
6. Deploy gateway & frontend
7. Configure external API integrations

### 7.7 Monitoring & Health Checks

**Health Endpoints:**
- `/health` - Overall system health
- `/api/health` - Backend API status
- `/auth/health` - Auth service status
- `/rag/health` - RAG service status

**Checks Included in docker-compose.yml:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:PORT/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**Monitoring Dashboard:**
- Railway Observability → View logs, CPU, memory
- Set Slack alerts for service failures

### 7.8 Rollback Strategy

**Local (Docker Compose):**
```bash
docker compose down -v          # Stop & remove volumes
docker compose build --no-cache # Rebuild from clean state
docker compose up               # Restart
```

**Cloud (Railway):**
- Auto-redeploy to last healthy commit
- View deployment history → Rollback button
- Manual rollback: Push previous version to git main

---

## 8. Implementation Roadmap

### Phase 1: MVP (Weeks 1-8)
- ✅ User login & project access
- ✅ Document upload (recording, email, document)
- ✅ STT processing via ElevenLabs
- ✅ Auto-generate meeting minutes & BRD drafts
- ✅ Version control & approval workflows
- ✅ RAG knowledge base with chatbot
- ✅ Daily backlog scan + Telegram notifications
- ✅ Docker Compose deployment to Railway

### Phase 2: Extended Features (Weeks 9-16)
- 🔲 Contract/clause analysis & risk flagging
- 🔲 Cost analysis functionality
- 🔲 Advanced RAG (multi-modal, clustering)
- 🔲 Enterprise scaling (Qdrant clustering, DB replicas)
- 🔲 Analytics dashboard
- 🔲 Slack integration

### Phase 3: Production Hardening (Weeks 17+)
- 🔲 Load testing & performance tuning
- 🔲 Security audit & penetration testing
- 🔲 Enterprise SSO (SAML/OAuth2)
- 🔲 Audit log archival
- 🔲 24/7 monitoring & alerting

---

## 9. Success Criteria

### Functional
- [ ] All 6 core modules working end-to-end
- [ ] 7 AI agents functioning with clear role division
- [ ] Document generation accuracy >85%
- [ ] Knowledge base returning relevant results
- [ ] Approval workflows completing within SLA

### Non-Functional
- [ ] Response time <2 sec for web UI
- [ ] STT processing <5 min/hour of audio
- [ ] Uptime >95% during business hours
- [ ] No critical security vulnerabilities
- [ ] Deployment completed on Railway with TLS

### User Adoption
- [ ] Core team trained and sign-off
- [ ] First 5 projects onboarded
- [ ] Weekly backlog scan running reliably
- [ ] Feedback loop established

---

## 10. Open Questions & Clarifications

1. **Approval Workflow Complexity:** How many approval levels? Sequential or parallel?
   - Answer: Typically 2-3 levels (BA → PM → Business Owner for BRD)

2. **Data Retention Policy:** How long to keep archived versions?
   - Answer: 12 months compliance minimum

3. **PII Sensitivity:** Define which fields are considered PII in your context?
   - Answer: Phone, SSN, email, financial figures

4. **Fallback for API Failures:** What's acceptable SLA when ElevenLabs is down?
   - Answer: Manual upload + offline processing (Phase 2)

5. **Multi-language Requirements:** Beyond Traditional Chinese + English?
   - Answer: Scope to these two for MVP

---

**End of Requirement Analysis**
