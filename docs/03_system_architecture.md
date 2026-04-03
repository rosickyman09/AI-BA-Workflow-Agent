# System Architecture: AI BA Agent
**Version:** 1.0  
**Date:** 2026-03-15  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Status:** MVP Phase 1 - Implementation Ready  
**Grounding:** Requirement Analysis (01), Agent Design (02), Skill Matrix (02b), Workflow Design (02c)

---

## 1. Folder Structure & Service Ownership

### Root Project Layout
```
ai-ba-agent/
├── frontend/                          # React/Next.js Web UI (Port 3000)
│   ├── public/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.tsx             # Home/Dashboard
│   │   │   ├── documents.tsx         # Document management
│   │   │   ├── approvals.tsx         # Approval dashboard
│   │   │   ├── knowledge-base.tsx    # RAG search interface
│   │   │   └── settings.tsx          # User preferences
│   │   ├── components/
│   │   │   ├── DocumentUpload.tsx
│   │   │   ├── ApprovalDashboard.tsx
│   │   │   ├── RAGChatbot.tsx
│   │   │   ├── VersionHistory.tsx
│   │   │   ├── RiskBadge.tsx
│   │   │   └── ConfidenceScore.tsx
│   │   ├── services/
│   │   │   ├── api.ts               # API client
│   │   │   ├── auth.ts              # Auth service
│   │   │   └── rag.ts               # RAG search service
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useDocuments.ts
│   │   │   ├── useApprovals.ts
│   │   │   └── useRAGSearch.ts
│   │   ├── styles/
│   │   │   └── globals.css
│   │   └── App.tsx
│   ├── package.json                 # Node dependencies
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── Dockerfile
│   └── README.md
│
├── backend/                          # Backend API Service (Port 5000)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py         # Document CRUD & upload
│   │   │   ├── approvals.py         # Approval workflow endpoints
│   │   │   ├── workflows.py         # Workflow status tracking
│   │   │   └── health.py            # Health check endpoint
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py  # Document orchestration
│   │   │   ├── approval_service.py  # Approval workflow logic
│   │   │   ├── workflow_service.py  # Workflow state management
│   │   │   ├── db_service.py        # Database operations
│   │   │   └── external_api.py      # External service calls
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py              # User ORM model
│   │   │   ├── project.py           # Project model
│   │   │   ├── document.py          # Document model
│   │   │   ├── approval.py          # Approval workflow model
│   │   │   └── audit_log.py         # Audit logging model
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── document.py          # DocumentUploadRequest, DocumentResponse
│   │   │   ├── approval.py          # ApprovalDecisionRequest, ApprovalResponse
│   │   │   └── workflow.py          # WorkflowStatusResponse
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── logging.py           # Structured logging middleware
│   │   │   ├── error_handling.py    # Error handler middleware
│   │   │   └── auth.py              # JWT validation middleware
│   │   └── config.py                # Configuration & environment
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── auth_service/                    # Auth Service (Port 5001)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI authentication app
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # Login, refresh, logout endpoints
│   │   │   ├── users.py             # User management endpoints
│   │   │   └── health.py            # Health endpoint
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── token_service.py     # JWT generation & validation
│   │   │   ├── user_service.py      # User CRUD & password hashing
│   │   │   ├── rbac_service.py      # Role-based access control
│   │   │   └── db_service.py        # PostgreSQL operations
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py              # User ORM model
│   │   │   └── role.py              # Role model
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # LoginRequest, TokenResponse
│   │   │   └── user.py              # UserProfile, UserCreateRequest
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   └── error_handling.py
│   │   └── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── rag_service/                     # RAG Service (Port 5002)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI orchestration app
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── extraction.py        # Data extraction endpoints
│   │   │   ├── rag.py               # Knowledge base search endpoints
│   │   │   ├── summarization.py     # Document generation endpoints
│   │   │   ├── validation.py        # Quality gate endpoints
│   │   │   ├── workflow.py          # Full workflow orchestration
│   │   │   └── health.py            # Health check
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py        # Base agent class
│   │   │   ├── routing_agent.py     # Request classifier
│   │   │   ├── extraction_agent.py  # Entity extraction
│   │   │   ├── rag_agent.py         # RAG verification
│   │   │   ├── summarization_agent.py # Document generation
│   │   │   ├── validation_agent.py  # Quality gate
│   │   │   ├── memory_agent.py      # Context management
│   │   │   └── security_agent.py    # Injection prevention
│   │   ├── skills/
│   │   │   ├── __init__.py
│   │   │   ├── extraction_skills.py     # 6 extraction skills
│   │   │   ├── rag_skills.py            # 5 RAG skills
│   │   │   ├── summarization_skills.py  # 5 summarization skills
│   │   │   ├── validation_skills.py     # 5 validation skills
│   │   │   ├── memory_skills.py         # 8 memory skills
│   │   │   └── security_skills.py       # 4 security skills
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── llm_service.py           # OpenRouter/DeepSeek integration
│   │   │   ├── embeddings_service.py    # Text embedding generation
│   │   │   ├── vector_db_service.py     # Qdrant client
│   │   │   ├── stt_service.py           # Speech-to-text (ElevenLabs, Deepgram)
│   │   │   ├── document_parser.py       # PDF, DOCX, XLSX parsing
│   │   │   ├── memory_service.py        # Redis + PostgreSQL memory
│   │   │   ├── db_service.py            # PostgreSQL operations
│   │   │   └── external_apis.py         # Gmail, Google Drive, Sheets, Telegram
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── llm_inference.py         # T001 - LLM tool
│   │   │   ├── document_parser.py       # T003 - PDF/DOCX parser
│   │   │   ├── json_validator.py        # T004 - JSON schema validator
│   │   │   ├── pattern_matcher.py       # T005 - Regex pattern matcher
│   │   │   ├── ocr_extractor.py         # T006 - OCR image extraction
│   │   │   ├── qdrant_client.py         # T007 - Vector DB client
│   │   │   ├── reranker.py              # T008 - Cross-encoder reranking
│   │   │   ├── embedder.py              # T010 - Text embedding model
│   │   │   └── [... more tools T011-T024]
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── extraction.py
│   │   │   ├── rag.py
│   │   │   ├── summarization.py
│   │   │   └── workflow.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   └── error_handling.py
│   │   └── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── gateway/                         # Nginx Gateway (Port 80/443)
│   ├── nginx.conf                   # Main configuration
│   ├── conf.d/
│   │   ├── upstream.conf            # Upstream service definitions
│   │   ├── routing.conf             # Route rules
│   │   ├── ssl.conf                 # SSL/TLS configuration
│   │   ├── security.conf            # Security headers
│   │   └── rate_limiting.conf       # Rate limit zones
│   ├── certs/
│   │   ├── cert.pem                 # SSL certificate
│   │   └── key.pem                  # SSL private key
│   ├── Dockerfile
│   └── README.md
│
├── infra/                           # Infrastructure & DevOps
│   ├── docker-compose.yml           # Multi-container orchestration
│   ├── .env.example                 # Configuration template
│   ├── migrations/
│   │   ├── 001_initial_schema.sql   # PostgreSQL DDL
│   │   ├── 002_add_indexes.sql      # Performance indexes
│   │   └── 003_seed_data.sql        # Test data
│   ├── backup/
│   │   ├── backup.sh                # Database backup script
│   │   └── restore.sh               # Database restore script
│   ├── monitoring/
│   │   ├── prometheus.yml           # Prometheus config (Phase 2)
│   │   └── grafana_dashboards/      # Grafana dashboards (Phase 2)
│   └── README.md
│
├── docs/                            # Documentation
│   ├── 01_requirement_analysis.md   # Business requirements (1100 lines)
│   ├── 02_agent_design.md           # Agent architecture (1200 lines)
│   ├── 02b_agent_skill_matrix.md    # Skill mappings (6000 lines)
│   ├── 02c_workflow_design.md       # Workflow orchestration (8500 lines)
│   ├── 03_system_architecture.md    # This document (12000 lines)
│   ├── 04_deployment_guide.md       # Railway deployment
│   ├── 05_api_reference.md          # API documentation
│   ├── 06_runbook.md                # Operational guide
│   └── ARCHITECTURE.md              # High-level overview
│
├── requirements/                    # Requirements & planning
│   └── [planning documents]
│
├── transformed_doc/                 # Reference documents
│   └── [filled requirement templates]
│
├── QUICKSTART.md                    # 5-minute setup guide
├── README.md                        # Project overview
├── docker-compose.yml               # Symlink to infra/docker-compose.yml
└── .env.example                     # Environment template
```

### Service Ownership Matrix

| Component | Service Owner | Port | Type | Responsibility |
|-----------|---------------|------|------|-----------------|
| Frontend | N/A | 3000 | Web UI | React/Next.js web application |
| Backend API | backend | 5000 | FastAPI | Document orchestration, workflow management |
| Auth Service | auth_service | 5001 | FastAPI | JWT authentication, RBAC, user management |
| RAG Service | rag_service | 5002 | FastAPI | AI agent orchestration, LLM integration |
| Gateway | gateway | 80/443 | Nginx | Reverse proxy, TLS, routing, rate limiting |
| PostgreSQL | infra | 5432 | Database | Relational data storage |
| Qdrant | infra | 6333 | Vector DB | Embeddings storage & semantic search |
| Redis | infra | 6379 | Cache | Session cache, rate limit counters |

---

## 2. Frontend Architecture

### Technology Stack
- **Framework:** Next.js 14 (React 18 + TypeScript)
- **Styling:** Tailwind CSS 3.x
- **State Management:** React Context API + SWR
- **Build:** Next.js SSG + static export → Nginx
- **Package Manager:** npm with lock file

### Pages & Routes

#### `/` — Home / Dashboard
- Welcome screen for authenticated users
- Quick stats (pending approvals, recent documents, KB hits)
- Navigation to main features

#### `/documents` — Document Management
- Upload audio/PDF/Word/Excel files
- View document status (draft, pending, approved, published)
- Version history with change tracking
- Download generated documents

#### `/approvals` — Approval Dashboard
- List pending approvals for user
- View approval workflows (current step, next reviewer)
- Approve/reject with comments
- SLA tracking (time remaining)

#### `/knowledge-base` — RAG Search Interface
- Semantic search input
- Search results with source citations
- Confidence scores per result
- "Similar documents" browser

#### `/settings` — User Preferences
- Account settings
- Project selection & role display
- Language preference (Chinese/English)
- Approval threshold configuration

### Component Structure

```
src/components/
├── DocumentUpload/
│   ├── DocumentUpload.tsx           # File upload form
│   ├── ProgressBar.tsx              # Upload progress
│   └── FilePreview.tsx              # File preview modal
│
├── ApprovalDashboard/
│   ├── ApprovalList.tsx             # Pending approvals table
│   ├── ApprovalDetail.tsx           # Approval detail modal
│   ├── SLAIndicator.tsx             # SLA countdown
│   └── DecisionForm.tsx             # Approve/reject form
│
├── RAGChatbot/
│   ├── SearchInput.tsx              # Search bar
│   ├── ResultsList.tsx              # Search results
│   ├── SourceCitation.tsx           # Citation with link
│   └── ConfidenceScore.tsx          # Confidence indicator
│
├── VersionHistory/
│   ├── VersionTimeline.tsx          # Version timeline
│   ├── VersionDiff.tsx              # Side-by-side comparison
│   └── VersionRestore.tsx           # Restore to previous version
│
├── Layout/
│   ├── Header.tsx                   # Top navigation
│   ├── Sidebar.tsx                  # Left sidebar menu
│   ├── Footer.tsx                   # Footer
│   └── MainLayout.tsx               # Main layout wrapper
│
├── Auth/
│   ├── LoginForm.tsx                # Login page
│   ├── ProtectedRoute.tsx           # Protected route guard
│   └── AuthProvider.tsx             # Auth context provider
│
└── Common/
    ├── Button.tsx
    ├── Modal.tsx
    ├── Badge.tsx
    ├── Toast.tsx
    └── LoadingSpinner.tsx
```

### Services Layer

**api.ts** - Axios/fetch wrapper
```typescript
class APIClient {
  async uploadDocument(file: File): Promise<DocumentResponse>
  async getDocuments(projectId: string): Promise<Document[]>
  async submitApproval(approvalId: string, decision): Promise<Result>
  async searchKnowledgeBase(query: string): Promise<SearchResults>
}
```

**auth.ts** - JWT authentication
```typescript
class AuthService {
  async login(email: string, password: string): Promise<TokenResponse>
  async logout(): Promise<void>
  async refreshToken(): Promise<TokenResponse>
  async getCurrentUser(): Promise<UserProfile>
}
```

**rag.ts** - RAG search
```typescript
class RAGService {
  async search(query: string, topK: number): Promise<SearchResults>
  async getCitations(docId: string): Promise<Citation[]>
  async getSimilarDocuments(docId: string): Promise<Document[]>
}
```

### Hooks

```typescript
// useAuth.ts
const useAuth = () => ({
  isAuthenticated: boolean
  user: UserProfile | null
  login: (email, password) => Promise<void>
  logout: () => Promise<void>
})

// useDocuments.ts
const useDocuments = (projectId: string) => ({
  documents: Document[]
  loading: boolean
  error: Error | null
  upload: (file: File) => Promise<void>
  refresh: () => Promise<void>
})

// useApprovals.ts
const useApprovals = (projectId: string) => ({
  pendingApprovals: ApprovalItem[]
  totalCount: number
  approve: (approvalId, comments) => Promise<void>
  reject: (approvalId, reason) => Promise<void>
})

// useRAGSearch.ts
const useRAGSearch = () => ({
  searching: boolean
  results: SearchResult[]
  search: (query) => Promise<void>
  clearResults: () => void
})
```

### Build Process

**Development:**
```bash
next dev  # Port 3000, hot reload
```

**Production:**
```bash
next build           # Next.js SSG + static export
next export          # Output to ./out/ folder
# Copy ./out contents to Nginx html/
```

**Docker:**
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/out /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

---

## 3. Backend Services Architecture

### 3.1 Backend API Service (Port 5000)

**Purpose:** Document orchestration, workflow routing, approval management

**Key Responsibilities:**
1. Document upload reception & validation
2. Workflow state tracking (current stage, approver assignments)
3. Approval request creation & status updates
4. HITL decision routing (approve, reject, escalate)
5. Version control & audit logging
6. N8N/Cron integration for async tasks

**Project Structure:**
```
backend/
app/
├── main.py
├── routers/
│   ├── documents.py      # POST /api/documents/upload, GET /api/documents/{id}
│   ├── approvals.py      # GET /api/approvals/pending, POST /api/approvals/{id}/approve
│   ├── workflows.py      # GET /api/workflow/{id}/status
│   └── health.py         # GET /health
├── services/
│   ├── document_service.py    # Document CRUD, upload orchestration
│   ├── approval_service.py    # Approval workflow state machine
│   ├── workflow_service.py    # Workflow status tracking
│   ├── rag_service_client.py  # REST calls to rag_service:5002
│   ├── db_service.py          # SQLAlchemy session management
│   └── external_api.py        # n8n, Telegram, Gmail API calls
├── models/
│   ├── user.py
│   ├── project.py
│   ├── document.py
│   ├── approval.py
│   └── audit_log.py
├── schemas/
│   ├── document.py        # DocumentUploadRequest, DocumentResponse
│   ├── approval.py        # ApprovalDecisionRequest
│   └── workflow.py        # WorkflowStatusResponse
├── middleware/
│   ├── logging.py         # Structured JSON logging
│   ├── error_handling.py  # Exception handlers
│   └── auth.py            # JWT bearer token validation
└── config.py              # Settings from environment
```

**Key Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/documents/upload` | POST | Queue document for processing |
| `/api/documents/{doc_id}` | GET | Retrieve document metadata |
| `/api/documents/{doc_id}/versions` | GET | List document versions |
| `/api/workflow/{workflow_id}` | GET | Get workflow status |
| `/api/approvals/pending` | GET | Fetch pending approvals (project-scoped) |
| `/api/approvals/{approval_id}/approve` | POST | Approve with comments |
| `/api/approvals/{approval_id}/reject` | POST | Reject with feedback |
| `/api/health` | GET | Service health check |

**Database Interactions:**
- Reads/writes: documents, document_versions, approval_workflows, approval_decisions
- Audit logs all actions for compliance

### 3.2 Auth Service (Port 5001)

**Purpose:** JWT authentication, user/role management, RBAC

**Key Responsibilities:**
1. User login (email/password) with bcrypt validation
2. JWT token generation (1-hour expiry) + refresh tokens (30-day expiry)
3. Token validation & refresh via middleware
4. User profile management (email, role, projects)
5. Role-based permission checks (per endpoint)
6. Token blacklist for logout

**Project Structure:**
```
auth_service/
app/
├── main.py
├── routers/
│   ├── auth.py         # POST /auth/login, /auth/refresh, /auth/logout
│   ├── users.py        # GET /auth/me, PATCH /auth/profile
│   └── health.py       # GET /auth/health
├── services/
│   ├── token_service.py   # JWT token gen/validation
│   ├── user_service.py    # User CRUD, password hashing (bcrypt)
│   ├── rbac_service.py    # Permission checks
│   ├── db_service.py      # PostgreSQL queries
│   └── cache_service.py   # Redis token storage
├── models/
│   ├── user.py            # User ORM model
│   └── role.py            # Role definitions
├── schemas/
│   ├── auth.py            # LoginRequest, TokenResponse
│   └── user.py            # UserProfile, UserUpdateRequest
└── config.py
```

**Key Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/login` | POST | Email/password authentication |
| `/auth/refresh` | POST | Refresh access token |
| `/auth/me` | GET | Get current user profile |
| `/auth/logout` | POST | Invalidate refresh token |
| `/auth/health` | GET | Health check |

**JWT Token Payload:**
```json
{
  "sub": "user-123",
  "email": "user@example.com",
  "role": "ba",
  "projects": [
    {"project_id": "proj-001", "role": "ba"},
    {"project_id": "proj-002", "role": "viewer"}
  ],
  "exp": 1705584000
}
```

**RBAC Model:**

| Global Role | Project Roles |
|-------------|---------------|
| Admin | Project Owner, BA, PM, Business Owner, Legal, Finance, Viewer |
| ProjectOwner | BA, PM, Business Owner, Legal, Finance, Viewer |
| (none) | BA (default), PM, Business Owner, Legal, Finance, Viewer |

**Permission Matrix:**
- **Admin:** Full access to all endpoints
- **ProjectOwner:** Can manage project users & settings
- **BA:** Can upload docs, view approvals
- **PM:** Can view workflows, assign approvers
- **Legal/Finance:** Approval authority for their domain
- **Viewer:** Read-only access

### 3.3 RAG Service (Port 5002)

**Purpose:** AI agent orchestration, RAG search, document generation

**Key Responsibilities:**
1. Route incoming requests to appropriate agent
2. Manage 7 AI agents with state handoff via PostgreSQL
3. Execute extraction, RAG search, summarization, validation
4. LLM API calls (OpenRouter/DeepSeek)
5. Vector DB operations (Qdrant embeddings)
6. Memory management (Redis + PostgreSQL)
7. Security checks (prompt injection prevention)

**Project Structure:**
```
rag_service/
app/
├── main.py                      # FastAPI orchestration app
├── routers/
│   ├── extraction.py            # POST /rag/extract
│   ├── rag.py                   # POST /rag/search
│   ├── summarization.py         # POST /rag/summarize
│   ├── validation.py            # POST /rag/validate
│   ├── workflow.py              # POST /rag/workflow/execute (full pipeline)
│   └── health.py                # GET /rag/health
│
├── agents/
│   ├── base_agent.py            # Abstract base class
│   ├── routing_agent.py         # Request classification
│   ├── extraction_agent.py      # Data extraction from transcript
│   ├── rag_agent.py             # RAG verification agent
│   ├── summarization_agent.py   # Document generation
│   ├── validation_agent.py      # Quality gate
│   ├── memory_agent.py          # Context retrieval
│   └── security_agent.py        # Injection prevention
│
├── skills/
│   ├── extraction_skills.py
│   │   ├── audio_transcription
│   │   ├── entity_extraction
│   │   ├── email_parsing
│   │   ├── document_parsing
│   │   ├── ocr_text_extraction
│   │   └── data_validation_initial
│   ├── rag_skills.py
│   │   ├── kb_semantic_search
│   │   ├── claim_grounding_check
│   │   ├── source_citation_generation
│   │   ├── result_reranking
│   │   └── confidence_scoring_rag
│   ├── summarization_skills.py
│   │   ├── meeting_minutes_generation
│   │   ├── brd_urs_generation
│   │   ├── digest_generation
│   │   ├── document_formatting
│   │   └── citation_integration
│   ├── validation_skills.py
│   │   ├── format_compliance_check
│   │   ├── risk_detection
│   │   ├── confidence_score_aggregation
│   │   ├── business_rule_validation
│   │   └── redundancy_check
│   ├── memory_skills.py
│   │   ├── conversation_store_short_term (Redis)
│   │   ├── conversation_retrieve_short_term (Redis)
│   │   ├── conversation_store_long_term (PostgreSQL)
│   │   ├── conversation_retrieve_long_term (PostgreSQL)
│   │   ├── workflow_state_store (PostgreSQL)
│   │   ├── workflow_state_retrieve (PostgreSQL)
│   │   ├── user_preferences_store
│   │   └── user_preferences_retrieve
│   └── security_skills.py
│       ├── pattern_matching_injection
│       ├── llm_based_detection
│       ├── security_logging
│       └── user_feedback_generation
│
├── services/
│   ├── llm_service.py              # OpenRouter/DeepSeek API
│   ├── embeddings_service.py       # Text embedding generation
│   ├── vector_db_service.py        # Qdrant client & operations
│   ├── stt_service.py              # ElevenLabs Scribe v2 + Deepgram
│   ├── document_parser.py          # PDF/DOCX/XLSX parsing + OCR
│   ├── memory_service.py           # Redis + PostgreSQL memory ops
│   ├── db_service.py               # PostgreSQL queries
│   └── external_apis.py            # Gmail, Drive, Sheets, Telegram
│
├── tools/
│   ├── llm_inference.py            # T001
│   ├── document_parser.py          # T003
│   ├── json_validator.py           # T004
│   ├── pattern_matcher.py          # T005
│   ├── ocr_extractor.py            # T006
│   ├── qdrant_client.py            # T007
│   ├── reranker.py                 # T008
│   ├── embedder.py                 # T010
│   ├── formatter.py                # T011
│   └── [... T012-T024 tools]
│
├── schemas/
│   ├── extraction.py
│   ├── rag.py
│   ├── summarization.py
│   ├── validation.py
│   └── workflow.py
└── config.py
```

**Key Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/rag/extract` | POST | Data Extraction Agent |
| `/rag/search` | POST | RAG semantic search |
| `/rag/summarize` | POST | Summarization Agent |
| `/rag/validate` | POST | Validation Agent |
| `/rag/memory/{user_id}` | GET | Memory Agent context |
| `/rag/security-check` | POST | Prompt injection detection |
| `/rag/workflow/execute` | POST | Full pipeline orchestration |
| `/rag/health` | GET | Health check |

**Agent Orchestration Workflow (MVP - Synchronous):**

```
1. Request received at /rag/workflow/execute
2. Routing Agent: Classify doc_type → route to appropriate agent sequence
3. Data Extraction Agent: Parse transcript/document → entities
   └─ Stores state in agent_state table
4. RAG Verification Agent: Cross-reference KB → citations & confidence
   └─ Retrieves parent state, updates handoff data
5. Summarization Agent: Generate structured document
   └─ Uses RAG results + extracted entities
6. Validation Agent: Quality gate → risk flags, confidence score
   └─ Retrieves business rules from PostgreSQL
7. Memory Agent: Log workflow state for future reference
   └─ Stores to Redis (short-term) + PostgreSQL (long-term)
8. Return: Document + citations + confidence + risk_flags to Backend API
9. Backend API: Routes to HITL approval workflow
```

---

## 4. API Gateway Architecture

### Gateway Purpose & Responsibility

**Nginx Reverse Proxy** (Port 80/443)
- Single external entry point (80/443)
- Routes traffic to internal services (5000-5002)
- TLS/SSL termination
- Rate limiting per endpoint
- Security headers (HSTS, CSP, X-Frame-Options)
- Static frontend serving
- Health check aggregation

### Gateway Configuration Structure

```
gateway/
├── nginx.conf              # Main config (worker processes, events, http)
├── conf.d/
│   ├── upstream.conf       # Upstream service definitions
│   ├── routing.conf        # Location blocks for routing
│   ├── ssl.conf            # SSL/TLS settings
│   ├── security.conf       # Security headers
│   └── rate_limiting.conf  # Rate limit zones
├── certs/
│   ├── cert.pem            # SSL certificate
│   └── key.pem             # SSL private key
└── Dockerfile
```

### Routing Configuration

```nginx
# Upstream service definitions
upstream frontend {
    server frontend:3000;
}

upstream backend_api {
    server backend:5000;
}

upstream auth_service {
    server auth_service:5001;
}

upstream rag_service {
    server rag_service:5002;
}

# HTTPS server block
server {
    listen 443 ssl http2;
    
    # SSL/TLS configuration
    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Frontend routes
    location / {
        proxy_pass http://frontend;
    }
    
    # Backend API with rate limiting
    location /api/ {
        limit_req zone=api burst=50 nodelay;
        proxy_pass http://backend_api;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }
    
    # Document upload (5 requests/minute)
    location /api/documents/upload {
        limit_req zone=upload burst=5 nodelay;
        proxy_pass http://backend_api;
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # Auth service
    location /auth/ {
        limit_req zone=auth burst=20 nodelay;
        proxy_pass http://auth_service;
    }
    
    # RAG service
    location /rag/ {
        limit_req zone=api burst=50 nodelay;
        proxy_pass http://rag_service;
    }
}
```

### Rate Limiting Configuration

```nginx
# Rate limit zones
limit_req_zone $binary_remote_addr zone=general:10m rate=100r/s;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=upload:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;
```

| Zone | Rate | Purpose |
|------|------|---------|
| general | 100req/sec | Global limit |
| api | 30req/sec | API endpoints |
| upload | 5req/min | Document upload |
| auth | 10req/min | Authentication |

### Security Headers

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline';" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
```

---

## 5. Database Schema & Design

### PostgreSQL (Port 5432)

**Core Purpose:** Relational data storage for transactional data with audit trail

**Schema Overview:**

### 5.1 Core Tables

#### users
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,              -- bcrypt hashed
    role VARCHAR(50) NOT NULL DEFAULT 'ba',          -- admin, ba, pm, business_owner, legal, finance, viewer
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### projects
```sql
CREATE TABLE projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(user_id),
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',              -- active, archived
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### user_projects (RBAC Junction Table)
```sql
CREATE TABLE user_projects (
    user_id UUID NOT NULL REFERENCES users(user_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    role VARCHAR(50) NOT NULL,                       -- ba, pm, business_owner, legal, finance, viewer (project-specific)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, project_id)
);
```

#### documents
```sql
CREATE TABLE documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    title VARCHAR(500) NOT NULL,
    doc_type VARCHAR(100),                           -- meeting_minutes, brd, urs, contract, email_digest
    status VARCHAR(50) DEFAULT 'draft',              -- draft, pending_approval, approved, published
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash VARCHAR(255),                        -- For deduplication detection
    google_drive_link TEXT,                          -- URL to original file
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### document_versions
```sql
CREATE TABLE document_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    content TEXT NOT NULL,                           -- Full document content
    content_hash VARCHAR(255),
    created_by UUID NOT NULL REFERENCES users(user_id),
    approval_status VARCHAR(50) DEFAULT 'pending',  -- pending, approved, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### approval_workflows
```sql
CREATE TABLE approval_workflows (
    workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    version_id UUID NOT NULL REFERENCES document_versions(version_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    current_step INT DEFAULT 1,                      -- Current approval stage
    total_steps INT,                                 -- Total approval steps
    status VARCHAR(50) DEFAULT 'in_progress',        -- in_progress, approved, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### approval_decisions
```sql
CREATE TABLE approval_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES approval_workflows(workflow_id),
    step_number INT NOT NULL,
    approver_id UUID NOT NULL REFERENCES users(user_id),
    decision VARCHAR(50) NOT NULL,                   -- approved, rejected, pending
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### audit_logs
```sql
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(project_id),
    action VARCHAR(100) NOT NULL,                   -- create, update, approve, publish
    entity_type VARCHAR(100),                        -- document, approval, workflow
    entity_id UUID,                                  -- Reference to entity
    user_id UUID NOT NULL REFERENCES users(user_id),
    old_values JSONB,                                -- Previous state
    new_values JSONB,                                -- New state
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_project_id ON audit_logs(project_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

### 5.2 Agent & Workflow State Tables

#### agent_state
```sql
CREATE TABLE agent_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES approval_workflows(workflow_id),
    agent_name VARCHAR(100) NOT NULL,                -- routing_agent, extraction_agent, etc.
    state_data JSONB NOT NULL,                       -- Extracted entities, LLM responses, etc.
    parent_agent VARCHAR(100),                       -- Previous agent in chain
    next_agent VARCHAR(100),                         -- Next agent to execute
    handoff_data JSONB,                              -- Data passed to next agent
    expires_at TIMESTAMP,                            -- TTL for cleanup
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_state_workflow_id ON agent_state(workflow_id);
CREATE INDEX idx_agent_state_expires_at ON agent_state(expires_at);
```

#### conversation_history
```sql
CREATE TABLE conversation_history (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    user_message TEXT NOT NULL,
    agent_response TEXT,
    context_data JSONB,                              -- Extracted context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_conversation_user_project ON conversation_history(user_id, project_id);
```

### 5.3 RAG & Embedding Metadata

#### document_embeddings
```sql
CREATE TABLE document_embeddings (
    embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    section_number INT,
    section_title VARCHAR(255),
    embedding_vector_id VARCHAR(255),                -- Reference to Qdrant collection point ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_embeddings_project_doc ON document_embeddings(project_id, doc_id);
```

### 5.4 Performance Indexes

```sql
CREATE INDEX idx_documents_project_id ON documents(project_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at);

CREATE INDEX idx_document_versions_doc_id ON document_versions(doc_id);
CREATE INDEX idx_document_versions_approval_status ON document_versions(approval_status);

CREATE INDEX idx_user_projects_user_id ON user_projects(user_id);
CREATE INDEX idx_user_projects_project_id ON user_projects(project_id);

CREATE INDEX idx_approval_workflows_doc_id ON approval_workflows(doc_id);
CREATE INDEX idx_approval_workflows_status ON approval_workflows(status);
CREATE INDEX idx_approval_workflows_project_id ON approval_workflows(project_id);
```

### 5.5 Data Isolation Strategy

**Project-Scoped Isolation:** All queries filter by `project_id` in WHERE clause
```sql
-- Example: Get documents for a project
SELECT * FROM documents WHERE project_id = $1;

-- Example with user role check
SELECT d.* FROM documents d
  INNER JOIN user_projects up ON d.project_id = up.project_id
  WHERE d.project_id = $1 AND up.user_id = $2;
```

---

## 6. RAG Infrastructure

### Qdrant Vector Database (Port 6333)

**Purpose:** Store document embeddings and enable semantic search

**Architecture:**

#### Collection: documents_embeddings
```json
{
  "name": "documents_embeddings",
  "config": {
    "vector_size": 1536,              // OpenAI text-embedding-3-large
    "distance": "Cosine",
    "storage": "Disk"                 // Persistent storage
  },
  "points": [
    {
      "id": "embedding-001",
      "vector": [0.123, 0.456, ...],  // 1536-dimensional embedding
      "payload": {
        "doc_id": "doc-uuid-001",
        "project_id": "proj-uuid-001",
        "section_number": 1,
        "section_title": "Executive Summary",
        "section_text": "Project overview...",
        "document_type": "brd",
        "created_at": "2026-03-15T10:00:00Z",
        "confidence": 0.85
      }
    }
  ]
}
```

### Embedding Pipeline

**1. Document Ingestion**
```
Raw Document
  ↓
[Chunking] → Split into ~500-token sections with 20% overlap
  ↓
[Embedding] → Generate 1536-dim vector per chunk (OpenAI API)
  ↓
[Storage] → Store in Qdrant with metadata (doc_id, project_id, section)
  ↓
[Indexing] → Create HNSW index for fast search
```

**2. Retrieval & Re-ranking**
```
User Query
  ↓
[Embedding] → Generate query embedding (same model)
  ↓
[Search] → Find top-5 similar vectors (cosine similarity > 0.3)
  ↓
[Filter] → Filter by project_id (data isolation)
  ↓
[Re-rank] → Cross-encoder re-ranking by relevance
  ↓
[Return] → Top-3 results with citations
```

**3. Confidence Scoring**
```
confidence = (
  0.4 * semantic_similarity_score +
  0.4 * claim_grounding_score +
  0.2 * citation_presence_factor
)

Interpretation:
- >= 0.8: HIGH confidence
- 0.6-0.79: MEDIUM confidence
- 0.4-0.59: LOW confidence
- < 0.4: NEEDS_CONFIRMATION
```

### Search Query Example

```python
# Query construction
query_vector = embedder.embed("payment processing requirements")
search_params = {
    "query": query_vector,
    "top": 5,
    "limit": 5,
    "with_payload": True,
    "query_filter": {
        "must": [
            {
                "key": "project_id",
                "match": {"value": "proj-001"}
            }
        ]
    }
}

# Qdrant search
results = qdrant_client.search(
    collection_name="documents_embeddings",
    query_vector=query_vector,
    query_filter=search_params["query_filter"],
    limit=5
)

# Results processing
for hit in results:
    citation = f"Document {hit.payload['doc_id']}, Section {hit.payload['section_number']}"
    confidence = calculate_confidence(hit.score, grounding_score, citation_exists)
    return_result(
        text=hit.payload['section_text'],
        citation=citation,
        confidence=confidence,
        similarity=hit.score
    )
```

### Fallback Strategy

If Qdrant unavailable:
```python
# Fallback to PostgreSQL full-text search
SELECT * FROM document_embeddings de
  INNER JOIN documents d ON de.doc_id = d.doc_id
  WHERE de.project_id = $1
    AND d.title @@ plainto_tsquery($2)
    OR d.doc_type IN ('brd', 'meeting_minutes')
  LIMIT 5;
```

---

## 7. AI Agent Integration

### Agent-to-Service Mapping

All 7 AI agents run within **rag_service** container (Port 5002):

| Agent | Service | Port | State Persistence |
|-------|---------|------|-------------------|
| Routing Agent | rag_service | 5002 | agent_state table |
| Data Extraction Agent | rag_service | 5002 | agent_state table |
| RAG Verification Agent | rag_service | 5002 | agent_state table |
| Summarization Agent | rag_service | 5002 | agent_state table |
| Validation Agent | rag_service | 5002 | agent_state table |
| Memory Agent | rag_service | 5002 | agent_state + Redis + PostgreSQL |
| Security Agent | api_service (middleware) | 5000 | audit_logs table |

### Agent Workflow State Machine

**State Storage in PostgreSQL (agent_state table):**

```json
{
  "state_id": "state-uuid-001",
  "workflow_id": "workflow-uuid-001",
  "agent_name": "extraction_agent",
  "state_data": {
    "extraction_result": {
      "decisions": [
        {"text": "Launch in Q2", "stakeholders": ["PM", "CEO"], "context": "timeline"}
      ],
      "action_items": [
        {"owner": "dev_team", "task": "Backend API", "due_date": "2026-04-30"}
      ],
      "requirements": [...],
      "risks": ["budget_overrun", "resource_constraint"]
    },
    "extraction_confidence": 0.87,
    "extraction_timestamp": "2026-03-15T10:30:00Z"
  },
  "parent_agent": "routing_agent",
  "next_agent": "rag_agent",
  "handoff_data": {
    "transcript": "full transcript...",
    "extracted_entities": {...},
    "confidence_scores": {...}
  },
  "expires_at": "2026-03-15T12:30:00Z",
  "created_at": "2026-03-15T10:00:00Z",
  "updated_at": "2026-03-15T10:30:00Z"
}
```

### Synchronous Handoff Mechanism (MVP)

```python
# Pseudo-code for workflow execution
def execute_workflow(workflow_id: str):
    # 1. Routing Agent
    routing_state = routing_agent.execute(request_data)
    save_agent_state(workflow_id, "routing_agent", routing_state)
    
    # 2. Data Extraction Agent
    extraction_state = extraction_agent.execute(
        parent_state=routing_state,
        handoff_data=routing_state.handoff_data
    )
    save_agent_state(workflow_id, "extraction_agent", extraction_state)
    
    # 3. RAG Verification Agent
    rag_state = rag_agent.execute(
        parent_state=extraction_state,
        handoff_data=extraction_state.handoff_data
    )
    save_agent_state(workflow_id, "rag_agent", rag_state)
    
    # 4. Summarization Agent
    summary_state = summarization_agent.execute(
        parents_states=[extraction_state, rag_state]
    )
    save_agent_state(workflow_id, "summarization_agent", summary_state)
    
    # 5. Validation Agent
    validation_state = validation_agent.execute(
        parent_state=summary_state
    )
    save_agent_state(workflow_id, "validation_agent", validation_state)
    
    # 6. Memory Agent (logging)
    memory_agent.store_workflow_state(workflow_id, validation_state)
    
    return validation_state.final_result
```

### Agent Constraints & Fallback Behaviors

**Extraction Agent:**
- Constraint: Recall >= 85%, Precision >= 95%
- Fallback: Mark uncertain items as "NEEDS_CONFIRMATION", no hallucination

**RAG Agent:**
- Constraint: Confidence >= 60% to mark "grounded"
- Fallback: If Qdrant down, use PostgreSQL keyword search

**Summarization Agent:**
- Constraint: No hallucinated content, preserve all numbers/dates
- Fallback: Use template-based fallback if LLM fails

**Validation Agent:**
- Constraint: No approval authority, only flagging
- Fallback: Return 0.5 (neutral) confidence if calculation fails

**Memory Agent:**
- Constraint: Redis TTL = 1 hour, PostgreSQL permanent
- Fallback: PostgreSQL if Redis down

---

## 8. Ports & Networking Strategy

### Multi-Port Architecture

**External (Host) Ports:**
```
80   → Gateway (HTTP redirect)
443  → Gateway (HTTPS)
```

**Internal (Docker Network) Ports:**
```
3000  → Frontend (React dev server)
5000  → Backend API (FastAPI)
5001  → Auth Service (FastAPI)
5002  → RAG Service (FastAPI)
5432  → PostgreSQL (relational DB)
6333  → Qdrant (vector DB)
6379  → Redis (cache)
```

### Docker Network Architecture

**Network Name:** `ai-ba-network` (custom bridge)

**Service-to-Service Communication:**
```
frontend:3000 ↔ gateway:443 (HTTP)
backend:5000 ↔ gateway:443 (HTTP)
auth_service:5001 ↔ gateway:443 (HTTP)
rag_service:5002 ↔ gateway:443 (HTTP)
backend:5000 ↔ auth_service:5001 (HTTP, internal)
backend:5000 ↔ rag_service:5002 (HTTP, internal)
rag_service:5002 ↔ postgres:5432 (TCP)
rag_service:5002 ↔ qdrant:6333 (HTTP)
rag_service:5002 ↔ redis:6379 (TCP)
```

### Port Exposure Strategy

**Services with port mappings (Host → Container):**
- Gateway: `80:80`, `443:443` (external access)

**Services without port mappings (Internal only):**
- Frontend: `expose: ["3000"]` (Docker network DNS only)
- Backend API: `expose: ["5000"]`
- Auth Service: `expose: ["5001"]`
- RAG Service: `expose: ["5002"]`
- PostgreSQL: `expose: ["5432"]`
- Qdrant: `expose: ["6333"]`
- Redis: `expose: ["6379"]`

**Docker Compose Configuration:**
```yaml
services:
  gateway:
    ports:
      - "80:80"
      - "443:443"
  backend:
    expose:
      - "5000"
  auth_service:
    expose:
      - "5001"
  rag_service:
    expose:
      - "5002"
  postgres:
    expose:
      - "5432"
  qdrant:
    expose:
      - "6333"
  redis:
    expose:
      - "6379"
```

### Firewall & Access Control

**External Access (Port 80/443):**
- ✅ Frontend (via gateway)
- ✅ API endpoints (via gateway)
- ❌ Databases (NOT exposed)

**Internal Access (Docker Network):**
- ✅ All services accessible via service name DNS
- ❌ Host machine cannot directly access internal ports (security)

---

## 9. Authentication & Authorization

### JWT Authentication Flow

**1. Login Request**
```
POST /auth/login
{
  "email": "user@example.com",
  "password": "password123"
}
```

**2. Auth Service Validation**
```python
# Lookup user in PostgreSQL
user = db.session.query(User).filter(User.email == email).first()

# Validate password (bcrypt)
if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
    raise UnauthorizedError("Invalid credentials")

# Generate JWT token
payload = {
    "sub": user.user_id,
    "email": user.email,
    "role": user.role,
    "projects": [
        {"project_id": p.project_id, "role": up.role}
        for p, up in user.projects
    ],
    "exp": datetime.utcnow() + timedelta(hours=1)
}
token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
```

**3. Token Response**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**4. API Request with Token**
```
GET /api/documents/pending
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**5. Backend Validation**
```python
# JWT middleware extracts token
@app.middleware("http")
async def verify_jwt(request: Request, call_next):
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]  # Extract token
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        request.state.user_id = payload["sub"]
        request.state.user_role = payload["role"]
        request.state.projects = payload["projects"]
    except jwt.ExpiredSignatureError:
        return JSONResponse({"error": "Token expired"}, status_code=401)
    
    return await call_next(request)
```

### Token Refresh Flow

**1. Refresh Request**
```
POST /auth/refresh
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**2. Auth Service Validation**
```python
# Validate refresh token (30-day expiry)
payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=["HS256"])

# Lookup token in Redis blacklist
if redis.exists(f"blacklist:{refresh_token}"):
    raise UnauthorizedError("Token revoked")

# Generate new access token
new_payload = {..., "exp": datetime.utcnow() + timedelta(hours=1)}
new_access_token = jwt.encode(new_payload, JWT_SECRET)
```

**3. Return New Token**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### RBAC Model

**Global Roles** (user.role):
- **admin** — Full access to all endpoints, user management
- **ba** — Default user role, document upload & basic access
- **projectowner** — Can manage project team
- **(implied ba)** — Default if no global role

**Project-Level Roles** (user_projects.role):

| Role | Documents | Approvals | Settings | Permissions |
|------|-----------|-----------|----------|-------------|
| ba | Create, view | View own pending | View own | Upload documents, submit for approval |
| pm | Create, view, edit | View, assign | Manage project | Orchestrate approvals, assign reviewers |
| business_owner | View, publish | Approve/reject | View | Final approval authority |
| legal | View | Approve/reject (legal domain) | View | Review & approve legal items |
| finance | View | Approve/reject (financial domain) | View | Review & approve financial items |
| viewer | View only | View only | None | Read-only access |

**Permission Matrix:**
```python
PERMISSIONS = {
    "document_upload": ["ba", "pm"],
    "document_edit": ["ba", "pm"],
    "document_publish": ["business_owner"],
    "approval_view": ["all_roles"],
    "approval_approve": ["business_owner", "legal", "finance"],
    "approval_assign": ["pm"],
    "project_settings": ["pm", "admin"],
    "user_management": ["admin"]
}
```

### RBAC Enforcement

**Endpoint Middleware Check:**
```python
def require_role(*allowed_roles):
    async def decorator(request: Request):
        user_role = request.state.user_role
        project_id = request.query_params.get("project_id")
        
        # Check global role
        if user_role in allowed_roles:
            return True
        
        # Check project-specific role
        if project_id:
            user_project = db.session.query(UserProject).filter(
                UserProject.user_id == request.state.user_id,
                UserProject.project_id == project_id
            ).first()
            
            if user_project and user_project.role in allowed_roles:
                return True
        
        raise ForbiddenError("Insufficient permissions")
    return decorator

@app.post("/api/approvals/{approval_id}/approve")
@require_role("business_owner", "legal", "finance")
async def approve_document(approval_id: str, request: Request):
    # Check user has permission for this approval
    approval = get_approval(approval_id)
    if approval.project_id not in [p["project_id"] for p in request.state.projects]:
        raise ForbiddenError("Not your project")
    
    # Process approval
    ...
```

---

## 10. Logging, Monitoring & Error Handling

### Structured Logging

**JSON Log Format:**
```json
{
  "timestamp": "2026-03-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "backend.services.document_service",
  "message": "Document uploaded successfully",
  "doc_id": "doc-uuid-001",
  "user_id": "user-uuid-123",
  "project_id": "proj-uuid-456",
  "duration_ms": 1250,
  "status": "success"
}
```

**Structured Logging Implementation (Python structlog):**
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "document_upload_complete",
    doc_id=doc_id,
    user_id=user_id,
    project_id=project_id,
    file_size_bytes=file_size,
    duration_ms=duration
)
```

**Logging Levels:**
- **DEBUG** — Verbose execution details (dev only)
- **INFO** — Normal operations (user actions, API calls)
- **WARNING** — Recoverable issues (retries, fallbacks)
- **ERROR** — Non-fatal errors (failed extraction, API timeouts)
- **CRITICAL** — System failures (DB down, unrecoverable errors)

### Standard Log Fields

Every log entry includes:
- `timestamp` — ISO 8601 format
- `level` — DEBUG, INFO, WARNING, ERROR, CRITICAL
- `logger` — Module/function name
- `message` — Human-readable message
- `user_id` — User making the request (except auth endpoints)
- `project_id` — Project context
- `duration_ms` — Operation duration
- `status` — success, failure, partial
- `error_code` — (if error)

### Error Handling & HTTP Status Codes

| HTTP | Scenario | Response |
|-----|----------|----------|
| 400 | Invalid input (schema validation fail) | `{"error": "Invalid file type", "code": "INVALID_INPUT"}` |
| 401 | Missing/invalid JWT token | `{"error": "Unauthorized", "code": "AUTH_REQUIRED"}` |
| 403 | Insufficient permissions | `{"error": "Forbidden", "code": "PERMISSION_DENIED"}` |
| 404 | Resource not found | `{"error": "Document not found", "code": "NOT_FOUND"}` |
| 429 | Rate limit exceeded | `{"error": "Too many requests", "code": "RATE_LIMIT"}` |
| 500 | Server error | `{"error": "Internal server error", "code": "SERVER_ERROR"}` |
| 503 | Service unavailable | `{"error": "Service temporarily unavailable", "code": "SERVICE_DOWN"}` |
| 504 | Gateway timeout | `{"error": "Request timeout", "code": "TIMEOUT"}` |

### Error Response Format

```json
{
  "error": "Payment processing requirements must be approved by Finance",
  "code": "VALIDATION_ERROR",
  "details": {
    "field": "risk_flags",
    "type": "financial",
    "severity": "high",
    "required_approver": "finance"
  },
  "request_id": "req-abc-123",
  "timestamp": "2026-03-15T10:30:45.123Z"
}
```

### Health Checks

**Endpoint:** `GET /health` (Gateway aggregates all)

```json
{
  "status": "healthy",
  "timestamp": "2026-03-15T10:30:45.123Z",
  "services": {
    "frontend": {"status": "healthy", "response_time_ms": 15},
    "backend_api": {"status": "healthy", "response_time_ms": 45},
    "auth_service": {"status": "healthy", "response_time_ms": 30},
    "rag_service": {"status": "healthy", "response_time_ms": 180},
    "postgres": {"status": "healthy", "response_time_ms": 20},
    "qdrant": {"status": "healthy", "response_time_ms": 100},
    "redis": {"status": "healthy", "response_time_ms": 5}
  },
  "overall": "healthy"
}
```

**Service Health Checks (Individual):**

Each container runs health check:
```bash
# Backend API
curl -f http://localhost:5000/health || exit 1

# Auth Service
curl -f http://localhost:5001/auth/health || exit 1

# RAG Service
curl -f http://localhost:5002/rag/health || exit 1

# PostgreSQL
pg_isready -U postgres || exit 1

# Qdrant
curl -f http://localhost:6333/health || exit 1

# Redis
redis-cli ping || exit 1
```

### Monitoring & Alerting

**Metrics to Track:**
- Request count & latency (p50, p95, p99)
- Error rate & error types
- Database query latency
- LLM API response time
- Vector DB search latency
- Cache hit rate (Redis)
- Disk space usage
- Memory usage

**Phase 2 Monitoring Stack:**
- **Prometheus** — Metrics collection
- **Grafana** — Dashboards
- **AlertManager** — Alerting
- **ELK Stack** — Log aggregation (Elasticsearch, Logstash, Kibana)
- **Sentry** — Error tracking

---

## 11. Containerization Strategy

### Multi-Container Architecture

**8 Containerized Services (MVP):**
1. **frontend** — React/Next.js web UI
2. **backend** — Document API service
3. **auth_service** — Authentication service
4. **rag_service** — AI agent orchestration
5. **gateway** — Nginx reverse proxy
6. **postgres** — PostgreSQL database
7. **qdrant** — Vector database
8. **redis** — Cache & session store

**Not Containerized (External APIs):**
- ElevenLabs Scribe v2 (STT)
- OpenRouter/DeepSeek (LLM)
- Google APIs (Gmail, Drive, Sheets)
- Telegram Bot API

### Dockerfile Strategy

**Multi-Stage Builds:** Reduce final image size by building in one stage, running in another

**Frontend Dockerfile:**
```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Runtime
FROM nginx:alpine
COPY --from=builder /app/out /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

**Backend Dockerfile:**
```dockerfile
# Stage 1: Build
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY app app/
ENV PYTHONUNBUFFERED=1
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/health')"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
```

### Image Size Targets

| Service | Base Image | Added Layers | Target Size | Build Time |
|---------|-----------|--------------|------------|-----------|
| frontend | nginx:alpine | React build | ~100 MB | 3 min |
| backend | python:3.11-slim | FastAPI deps | ~300 MB | 4 min |
| auth_service | python:3.11-slim | FastAPI, JWT | ~280 MB | 3 min |
| rag_service | python:3.11-slim | ML dependencies | ~800 MB | 8 min |
| gateway | nginx:alpine | Config only | ~50 MB | 1 min |

### Dependency Management

**Python (requirements.txt):**
```
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
pyjwt==2.8.1
passlib==1.7.4
bcrypt==4.1.1
httpx==0.25.2
```

**Node.js (package-lock.json):**
- Remove `^` and `~` for exact versions
- Commit lock file to git
- Use `npm ci` (clean install) in Docker

**Version Pinning Strategy:**
- Pin all dependencies to exact version (==)
- Review updates weekly
- Test major version upgrades in staging first

### Security: Image Scanning & Hardening

```bash
# Scan for vulnerabilities
docker scan backend:latest

# Non-root user in Dockerfile
RUN useradd -m appuser
USER appuser

# No secrets in image
COPY --chown=appuser:appuser app app/
```

---

## 12. Dockerfile Ownership & Locations

### Per-Service Dockerfiles

| Service | Path | Owned By | Base Image | Size |
|---------|------|----------|-----------|------|
| Frontend | `frontend/Dockerfile` | Frontend team | node:20-alpine | ~100 MB |
| Backend API | `backend/Dockerfile` | Backend team | python:3.11-slim | ~300 MB |
| Auth Service | `auth_service/Dockerfile` | Auth team | python:3.11-slim | ~280 MB |
| RAG Service | `rag_service/Dockerfile` | AI/ML team | python:3.11-slim | ~800 MB |
| Gateway | `gateway/Dockerfile` | DevOps team | nginx:alpine | ~50 MB |

### Building Images

**Manual Build:**
```bash
# FROM root directory
docker build -f backend/Dockerfile -t ai-ba-backend:latest ./backend
docker build -f auth_service/Dockerfile -t ai-ba-auth:latest ./auth_service
docker build -f rag_service/Dockerfile -t ai-ba-rag:latest ./rag_service
docker build -f gateway/Dockerfile -t ai-ba-gateway:latest ./gateway
docker build -f frontend/Dockerfile -t ai-ba-frontend:latest ./frontend
```

**Docker Compose Build:**
```bash
# FROM infra/ directory
docker-compose build
```

### Image Naming Convention

- **Registry:** (none for local, ghcr.io/your-org for production)
- **Repository:** `ai-ba-<service>`
- **Tag:** `latest`, `v0.1.0`, `dev`, `staging`, `prod`

Example: `ghcr.io/your-org/ai-ba-backend:v0.1.0`

---

## 13. Gateway & Reverse Proxy Design

### Nginx Configuration Architecture

**File Structure:**
```
gateway/
├── nginx.conf              # Main configuration (worker_processes, http block)
├── Dockerfile
├── conf.d/
│   ├── upstream.conf       # Upstream service definitions (backend, auth, rag)
│   ├── routing.conf        # Location blocks with proxy_pass rules
│   ├── ssl.conf            # SSL/TLS protocol settings
│   ├── security.conf       # Security headers (HSTS, CSP, X-Frame-Options)
│   └── rate_limiting.conf  # Rate limit zone definitions
└── certs/
    ├── cert.pem            # SSL certificate (self-signed or Let's Encrypt)
    └── key.pem             # SSL private key
```

### Upstream Service Definitions

```nginx
upstream frontend {
    server frontend:3000;
}

upstream backend_api {
    server backend:5000;
}

upstream auth_service {
    server auth_service:5001;
}

upstream rag_service {
    server rag_service:5002;
}
```

### Routing Rules

**HTTP → HTTPS Redirect:**
```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
```

**HTTPS Server Block:**
```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    # Frontend routes (/)
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Backend API routes (/api/*)
    location /api/ {
        limit_req zone=api burst=50 nodelay;
        proxy_pass http://backend_api;
        proxy_set_header Authorization $http_authorization;
    }
    
    # Document upload with higher rate limit
    location /api/documents/upload {
        limit_req zone=upload burst=5 nodelay;
        proxy_pass http://backend_api;
        proxy_buffering off;
    }
    
    # Auth service routes (/auth/*)
    location /auth/ {
        limit_req zone=auth burst=20 nodelay;
        proxy_pass http://auth_service;
    }
    
    # RAG service routes (/rag/*)
    location /rag/ {
        limit_req zone=api burst=50 nodelay;
        proxy_pass http://rag_service;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://backend_api;
    }
}
```

### SSL/TLS Configuration

**Development (Self-Signed):**
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout gateway/certs/key.pem \
  -out gateway/certs/cert.pem \
  -subj "/C=TW/ST=Taipei/L=Taipei/O=AI-BA/CN=localhost"
```

**Production (Let's Encrypt via Railway):**
- Railway provides automatic TLS certificates
- No action needed beyond deploying to Railway

**Nginx SSL Configuration:**
```nginx
ssl_certificate /etc/nginx/certs/cert.pem;
ssl_certificate_key /etc/nginx/certs/key.pem;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
```

### Security Headers

```nginx
# HSTS (Strict-Transport-Security)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# Prevent clickjacking
add_header X-Frame-Options "DENY" always;

# Prevent MIME type sniffing
add_header X-Content-Type-Options "nosniff" always;

# XSS protection (browser built-in)
add_header X-XSS-Protection "1; mode=block" always;

# Content Security Policy
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;

# Referrer Policy
add_header Referrer-Policy "no-referrer-when-downgrade" always;

# Permissions Policy
add_header Permissions-Policy "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()" always;
```

### Rate Limiting Configuration

```nginx
limit_req_zone $binary_remote_addr zone=general:10m rate=100r/s;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=upload:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;
```

**Per-Endpoint Rate Limiting:**

| Endpoint | Zone | Rate | Burst |
|----------|------|------|-------|
| `/api/*` | api | 30req/sec | 50 |
| `/api/documents/upload` | upload | 5req/min | 5 |
| `/auth/*` | auth | 10req/min | 20 |
| `/rag/*` | api | 30req/sec | 50 |

---

## 14. Internal vs External Port Visibility

### Port Visibility Matrix

| Port | Service | External Access | Docker Network | Purpose |
|------|---------|-----------------|-----------------|---------|
| 80 | Gateway | ✅ Yes | ✅ Yes | HTTP (redirect to HTTPS) |
| 443 | Gateway | ✅ Yes | ✅ Yes | HTTPS (TLS termination) |
| 3000 | Frontend | ❌ No | ✅ Yes | React development server |
| 5000 | Backend | ❌ No | ✅ Yes | Backend API |
| 5001 | Auth Service | ❌ No | ✅ Yes | Auth endpoints |
| 5002 | RAG Service | ❌ No | ✅ Yes | AI orchestration |
| 5432 | PostgreSQL | ❌ No | ✅ Yes | Database (Container network) |
| 6333 | Qdrant | ❌ No | ✅ Yes | Vector DB (Container network) |
| 6379 | Redis | ❌ No | ✅ Yes | Cache (Container network) |

### Docker Compose Port Configuration

```yaml
services:
  gateway:
    ports:                    # Host → Container mapping (external access)
      - "80:80"
      - "443:443"

  backend:
    expose:                   # Container network only (no host mapping)
      - "5000"

  auth_service:
    expose:
      - "5001"

  rag_service:
    expose:
      - "5002"

  postgres:
    expose:
      - "5432"

  qdrant:
    expose:
      - "6333"

  redis:
    expose:
      - "6379"
```

### Access from Outside Docker Network

**From Host Machine:**
```bash
# ✅ Accessible via gateway
curl https://localhost

# ❌ Not accessible (no port mapping)
curl http://localhost:5000  # Connection refused
curl http://localhost:5432  # Connection refused
```

**From Inside Docker Network:**
```bash
# Docker DNS names work for all services
docker exec -it backend bash
curl http://auth_service:5001/auth/health  # ✅ Works
curl http://postgres:5432                    # ✅ DNS resolves (TCP connection)
```

### Security Implications

**Benefits of Internal-Only Ports:**
- Backend services not directly exposed to internet
- Reduces attack surface
- Force all traffic through gateway (single choke point)
- Gateway handles rate limiting, security headers centrally

**Front-End Calling Backend Directly:**
- ❌ NOT possible (frontend can only reach gateway:443)
- Browser CORS blocked direct access to internal ports
- All API calls routed through gateway proxy

---

## 15. Docker Compose Service Orchestration

### Complete docker-compose.yml

**Location:** `infra/docker-compose.yml`

**Structure:**
```yaml
version: '3.8'

services:
  # Database Layer (initialization order)
  postgres:
    image: postgres:15-alpine
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck: [postgres health checks]
  
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: [qdrant_data:/qdrant/storage]
    healthcheck: [curl health checks]
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    healthcheck: [redis-cli ping]
  
  # Backend Services (depend on databases)
  auth_service:
    build: ../auth_service
    expose: ["5001"]
    depends_on: [postgres, redis]
    environment: [...]
    healthcheck: [...]
  
  backend:
    build: ../backend
    expose: ["5000"]
    depends_on: [postgres, redis, auth_service]
    environment: [...]
    healthcheck: [...]
  
  rag_service:
    build: ../rag_service
    expose: ["5002"]
    depends_on: [postgres, qdrant, redis]
    environment: [...]
    healthcheck: [...]
  
  # Frontend & Gateway
  frontend:
    build: ../frontend
    expose: ["3000"]
    healthcheck: [...]
  
  gateway:
    build: ../gateway
    ports: ["80:80", "443:443"]
    depends_on: [all services healthy]
    healthcheck: [...]

volumes:
  postgres_data:
  qdrant_data:
  redis_data:

networks:
  ai-ba-network:
    driver: bridge
```

### Service Dependencies & Startup Order

**Dependency Graph:**
```
postgres ─────┐
              ├─→ auth_service ─→ backend ─→ rag_service ─┐
qdrant ───────┤                                              ├─→ gateway
redis ────────┤                                              │
              └─→ frontend ──────────────────────────────────┘
```

**Docker Compose Dependency Resolution:**
```yaml
depends_on:
  postgres:
    condition: service_healthy     # Wait for postgres health check
  redis:
    condition: service_healthy     # Wait for redis health check
```

**Startup Sequence:**
1. postgres, qdrant, redis (parallel) — Wait for health checks
2. auth_service — Depends on postgres → waits
3. backend — Depends on postgres, auth_service → waits
4. rag_service — Depends on postgres, qdrant, redis → waits
5. frontend — No dependencies → starts immediately
6. gateway — Depends on all services healthy → waits for health checks

### Health Checks

**PostgreSQL:**
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
  interval: 10s
  timeout: 5s
  retries: 5
```

**Backend API:**
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:5000/health || exit 1"]
  interval: 15s
  timeout: 10s
  retries: 3
  start_period: 20s
```

**All Services:**
```yaml
healthcheck:
  test: [CMD, endpoint, or shell]
  interval: 30s         # Check every 30 seconds
  timeout: 10s          # Wait 10 seconds for response
  retries: 3            # Fail after 3 failed checks
  start_period: 60s     # Grace period before health checks (optional)
```

### Environment Variables

**Passed via .env file:**
```
DB_HOST=postgres
DB_NAME=ai_ba_db
DB_USER=postgres
DB_PASSWORD=your_password
JWT_SECRET=your_secret_min_32_chars
OPENROUTER_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

**Interpolation in docker-compose.yml:**
```yaml
environment:
  DB_NAME: ${DB_NAME:-ai_ba_db}
  DB_PASSWORD: ${DB_PASSWORD:-postgres}
  JWT_SECRET: ${JWT_SECRET}
```

### Volumes & Persistent Storage

**Named Volumes (Docker-managed):**
```yaml
volumes:
  postgres_data:
    driver: local
  qdrant_data:
    driver: local
  redis_data:
    driver: local

services:
  postgres:
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

**Volume Persistence:**
- Data survives container restarts
- Lost on `docker-compose down -v` (volume deletion)
- Backed up daily to S3 (Phase 2)

### Service Networking

**Custom Bridge Network:**
```yaml
networks:
  ai-ba-network:
    driver: bridge
```

**Service DNS Resolution (Inside Network):**
```
postgres:5432        # Resolves to postgres service
backend:5000         # Resolves to backend service
qdrant:6333          # Resolves to qdrant service
```

### Restart Policies

```yaml
restart_policy:
  condition: unless-stopped  # Restart on failure (except manual stop)
  delay: 5s                  # Wait 5s before restart
  max_attempts: 5            # Max 5 restart attempts
```

---

## 16. Volumes & Persistent Storage

### Storage Classification

| Component | Volume | Type | Persistence | Backup | Restore |
|-----------|--------|------|-------------|--------|---------|
| PostgreSQL | postgres_data | Named | ✅ Persistent | Daily snapshots | Manual via pg_dump |
| Qdrant | qdrant_data | Named | ✅ Persistent | Daily snapshots | Rebuild from docs |
| Redis | redis_data | Named | ✅ Optional | Not recommended | Ephemeral (auto-expire) |

### PostgreSQL Backup & Restore

**Backup Strategy:**
```bash
# Daily automated backup (cron job)
docker exec ai_ba_postgres pg_dump -U postgres ai_ba_db | \
  gzip > backups/ai_ba_db_$(date +%Y%m%d).sql.gz

# Upload to S3
aws s3 cp backups/ai_ba_db_*.sql.gz s3://your-bucket/backups/
```

**Restore from Backup:**
```bash
# Download from S3
aws s3 cp s3://your-bucket/backups/ai_ba_db_20260314.sql.gz .

# Restore to PostgreSQL
gunzip < ai_ba_db_20260314.sql.gz | \
  docker exec -i ai_ba_postgres psql -U postgres ai_ba_db
```

### Qdrant Backup & Restore

**Backup Strategy:**
```bash
# Daily snapshot backup
docker exec ai_ba_qdrant curl -X POST \
  http://localhost:6333/snapshots \
  -H "Content-Type: application/json"

# Results in: /qdrant/storage/snapshots/snapshot_*.tar
```

**Restore from Backup:**
```bash
# If Qdrant data lost, rebuild embeddings from PostgreSQL
python scripts/rebuild_qdrant_from_documents.py

# 1. Read all document_versions from PostgreSQL
# 2. Extract text chunks
# 3. Generate embeddings (OpenAI API)
# 4. Upload to Qdrant
# Estimated time: ~2-5 hours for 10k documents
```

### Redis Data Persistence

**Not backed up (ephemeral storage):**
- Session tokens (TTL 1 hour, auto-expire)
- Rate limit counters (TTL per time window)
- Temporary workflow state (replaced by PostgreSQL persistence)

**If Redis lost:**
- Users need to re-login (generate new tokens)
- Rate limits reset
- No data loss (workflow state persisted in PostgreSQL)

### Data Loss Impact Assessment

| Component Lost | Impact | Recovery Time |
|---|---|---|
| PostgreSQL | Critical — All data lost | 30-60 min (restore from backup) |
| Qdrant | Medium — RAG unavailable | 2-5 hours (rebuild from docs) |
| Redis | Low — Session reset | 5 min (users re-login) |

### Volume Cleanup

```bash
# View volumes
docker volume ls

# Remove unused volumes
docker volume prune

# Delete specific volume (data loss!)
docker volume rm ai_ba_network_postgres_data
```

### Disaster Recovery Plan

**RTO (Recovery Time Objective):** 1 hour
**RPO (Recovery Point Objective):** Last daily backup (24 hours)

**1. System Failure → Emergency Restore:**
```bash
# Stop all services
docker-compose down

# Restore PostgreSQL from latest backup
gunzip < backups/latest.sql.gz | docker exec -i ai_ba_postgres psql ...

# Restart services
docker-compose up -d

# Rebuild Qdrant embeddings (can run async, users can use PostgreSQL keyword search)
python scripts/rebuild_qdrant_from_documents.py &
```

**2. Data Corruption → Rollback:**
```bash
# Restore to backup from previous day
docker-compose down -v
# Restore databases
docker-compose up -d
```

---

## Summary & Deployment Readiness

### Architecture Completeness Checklist

✅ **Folder Structure** — Service ownership matrix defined
✅ **Frontend Architecture** — React/Next.js pages, components, services
✅ **Backend Services** — 4 independent FastAPI services
✅ **API Gateway** — Nginx reverse proxy with TLS, routing, security
✅ **Database Schema** — PostgreSQL DDL with 8 core tables + indexes
✅ **RAG Infrastructure** — Qdrant vector DB with embeddings pipeline
✅ **AI Agents** — 7 agents with state persistence & handoff mechanism
✅ **Port Strategy** — Multi-port architecture with clear visibility
✅ **Authentication** — JWT + RBAC with project-level roles
✅ **Logging & Monitoring** — Structured JSON logs + health checks
✅ **Containerization** — 8 containerized services with Dockerfiles
✅ **Docker Compose** — Complete multi-container orchestration
✅ **Volumes & Backup** — Persistent storage with backup strategy

### Next Steps for Implementation

1. **Clone Repository** — ai-ba-agent project ready for development
2. **Configure Environment** — Copy `.env.example` → `.env`, fill in API keys
3. **Start Docker Compose** — `docker-compose up -d` from infra/ folder
4. **Verify Services** — All health checks should pass
5. **Run Migrations** — PostgreSQL schema initialization
6. **Test APIs** — Login, upload document, search knowledge base
7. **Deploy to Railway** — Connect GitHub → Railway -> Deploy

### Performance Targets (MVP)

| Metric | Target | Notes |
|--------|--------|-------|
| Page Load Time | <2 sec | Frontend via CDN |
| API Response Time | <500ms | Excluding LLM calls |
| STT Processing | <5 min/hour | ElevenLabs async |
| Document Generation | <2 min | LLM inference |
| RAG Search Latency | <500ms | Semantic search |
| Concurrent Users | 20-50 | Internal team only |
| Uptime Target | 95% | Business hours |

### Scale Path (Phase 2+)

- **Horizontal Scaling:** Multiple backend replicas behind load balancer
- **Database Scaling:** PostgreSQL read replicas, Qdrant clustering
- **LLM Scaling:** Dedicated embedding service, model caching
- **Monitoring:** ELK Stack for log aggregation, Prometheus metrics
- **Enterprise Features:** SSO/SAML, advanced analytics, custom workflows

---

**End of System Architecture Document**

**Version:** 1.0  
**Status:** MVP Phase 1 - Implementation Ready  
**Last Updated:** 2026-03-15  
**Next Document:** 04_deployment_guide.md (Railway deployment instructions)
