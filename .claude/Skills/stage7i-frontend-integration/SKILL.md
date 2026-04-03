---
name: stage7i-frontend-integration
description: Implements the complete frontend integration connecting the UI to all backend services. Use this skill when the user wants to build the real login flow, implement JWT cookie storage, create a document upload UI with progress tracking, build an approval dashboard, implement a RAG chatbot UI with citations, or create a knowledge base page with document version history. Trigger when the user mentions "frontend integration", "real login", "JWT cookie", "upload UI", "approval dashboard", "RAG chatbot UI", "knowledge base page", "frontend connect backend", "document status polling", or wants to implement Stage 7I after notifications are working.
---

## Stage 7I — Agent Mode: Frontend Integration

### Purpose
Connect all frontend pages to real backend services — replacing any mock data or placeholder flows with live API calls. This stage implements real login with JWT cookie storage, document upload with status polling, approval dashboard with role-based display, RAG chatbot UI with citations, and knowledge base with version history.

> ⚠️ Do NOT change the architecture, docker-compose.yml, or port assignments. Implementation only.

---

### Prerequisites

- [ ] Stage 7H complete — notification module working
- [ ] Stage 7C complete — real auth + RBAC working
- [ ] `docs/03_system_architecture.md` exists (API contracts)
- [ ] `frontend/pages/login.tsx` exists (from Stage 7 scaffold)
- [ ] All backend endpoints working and tested
- [ ] Frontend running (port 3000)

---

### Step 1 — Switch to Agent Mode and Attach Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach both input files:
   ```
   docs/03_system_architecture.md
   frontend/pages/login.tsx
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Agent Mode):

```
Implement frontend integration — connect all pages to real backend APIs.

Task 1 — Real Login Flow:
- Connect login form to POST /auth/login
- Store JWT in httpOnly cookie (not localStorage)
- Redirect to dashboard on success
- Show error message on 401
- Implement logout: POST /auth/logout + clear cookie

Task 2 — Document Upload UI:
- Upload form: file input + project selector
- Show upload progress bar
- After upload: poll GET /api/documents/{id}/status
  every 3 seconds until COMPLETED or FAILED
- Display final status to user

Task 3 — Approval Dashboard:
- GET /api/approvals?status=pending → pending list
- Show approve/reject buttons only for users
  with required role (business_owner or admin)
- POST /api/approvals/{id}/approve on button click
- POST /api/approvals/{id}/reject with reason
- Auto-refresh list after action

Task 4 — RAG Chatbot UI:
- Text input for search query
- Project scope selector (dropdown)
- Call POST /rag/search
- Display results with citations [doc_id#section]
- Clickable citations → open source document

Task 5 — Knowledge Base Page:
- List all documents: GET /api/documents
- Show document status + version count
- Version history: GET /api/documents/{id}/versions
- Expandable version list per document

Do NOT change architecture or docker-compose.yml.

Create:
- frontend/pages/login.tsx (update with real flow)
- frontend/pages/documents.tsx
- frontend/pages/approvals.tsx
- frontend/pages/knowledge-base.tsx
- frontend/services/auth.ts
- frontend/services/documents.ts
- frontend/services/rag.ts
```

---

### Step 3 — Expected Output Files

```
frontend/
├── pages/
│   ├── login.tsx               ← Real login + JWT cookie
│   ├── documents.tsx           ← Upload UI + status polling
│   ├── approvals.tsx           ← Approval dashboard + RBAC display
│   └── knowledge-base.tsx      ← Doc list + version history
└── services/
    ├── auth.ts                 ← Login/logout API calls
    ├── documents.ts            ← Upload/status API calls
    └── rag.ts                  ← Search API calls
```

---

### Step 4 — API Endpoints Used by Frontend

| Page | Method | Endpoint | Auth |
|---|---|---|---|
| Login | POST | /auth/login | None |
| Login | POST | /auth/logout | Token |
| Documents | POST | /api/documents/upload | BA/Admin |
| Documents | GET | /api/documents/{id}/status | Token |
| Documents | GET | /api/documents | Token |
| Approvals | GET | /api/approvals?status=pending | Token |
| Approvals | POST | /api/approvals/{id}/approve | Approver |
| Approvals | POST | /api/approvals/{id}/reject | Approver |
| Knowledge Base | GET | /api/documents/{id}/versions | Token |
| RAG Chat | POST | /rag/search | Token |

---

### Step 5 — Acceptance Tests (Must All Pass)

#### Test 1 — Real Login Works
- Navigate to login page
- Enter `admin@ai-ba.local` / `password123`
- Expected: redirect to dashboard ✅
- Check: httpOnly cookie set in browser DevTools ✅

#### Test 2 — Upload + Status Polling
- Upload a PDF file
- Expected: progress bar shown → status polls → "COMPLETED" displayed ✅

#### Test 3 — Approval Dashboard RBAC
- Login as `ba1@ai-ba.local`
- Navigate to approvals page
- Expected: approve/reject buttons NOT visible for BA role ✅
- Login as `owner@ai-ba.local`
- Expected: approve/reject buttons visible ✅

#### Test 4 — RAG Search
- Enter query in chatbot
- Expected: results displayed with `[doc_id#section]` citations ✅

#### Test 5 — Mobile Responsive
- Open Chrome DevTools → toggle device toolbar
- Navigate all 4 pages on mobile viewport (375px)
- Expected: layout adapts, no horizontal scroll ✅

---

### Output

```
frontend/pages/login.tsx            ← Real JWT login
frontend/pages/documents.tsx        ← Upload + polling
frontend/pages/approvals.tsx        ← Role-aware dashboard
frontend/pages/knowledge-base.tsx   ← Docs + versions
frontend/services/auth.ts           ← Auth API layer
frontend/services/documents.ts      ← Documents API layer
frontend/services/rag.ts            ← RAG API layer
```

---

### Checklist

- [ ] Agent Mode activated before submitting prompt
- [ ] Both input files attached
- [ ] Login page connects to real `POST /auth/login`
- [ ] JWT stored in httpOnly cookie (NOT localStorage)
- [ ] 401 error shows user-friendly error message
- [ ] Logout clears cookie and redirects to login
- [ ] Upload form accepts file + project selection
- [ ] Status polling every 3 seconds until COMPLETED/FAILED
- [ ] Approval dashboard shows pending list from API
- [ ] Approve/reject buttons hidden for non-approver roles
- [ ] RAG search displays results with citations
- [ ] Citation format `[doc_id#section]` clickable
- [ ] Knowledge base page lists documents + versions
- [ ] All 5 pages mobile responsive (375px viewport)
- [ ] All 5 acceptance tests pass
- [ ] 🔒 All tests pass before proceeding to Stage 7J (E2E Testing)
