---
name: stage7g-approval-workflow
description: Implements the multi-step approval workflow with HITL triggers, version control, and audit logging. Use this skill when the user wants to build an approval system, implement multi-step role-based approval routing, add human-in-the-loop (HITL) triggers for high-risk content, implement document version control, record approval audit logs, or create approve/reject API endpoints. Trigger when the user mentions "approval workflow", "multi-step approval", "HITL", "human in the loop", "approve endpoint", "reject endpoint", "version control", "audit log", "approval routing", "document versions", or wants to implement Stage 7G after the RAG knowledge base is working.
---

## Stage 7G — Agent Mode: Approval Workflow Module

### Purpose
Build the complete approval workflow system: multi-step role hierarchy approvals, HITL triggers for high-risk content, document version control (every change = new version), and comprehensive audit logging of every approval action with approver identity and timestamp.

> ⚠️ Do NOT change the architecture, docker-compose.yml, or database schema. Implementation only.

---

### Prerequisites

- [ ] Stage 7F complete — RAG knowledge base working
- [ ] Stage 7C complete — RBAC middleware in place
- [ ] `docs/02c_workflow_design.md` exists (HITL trigger definitions)
- [ ] `docs/03_system_architecture.md` exists (RBAC section)
- [ ] PostgreSQL running with `approvals`, `document_versions`, `audit_logs` tables
- [ ] Backend RBAC middleware (require_approver) already implemented

---

### Step 1 — Switch to Agent Mode and Attach Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach both input files:
   ```
   docs/02c_workflow_design.md
   docs/03_system_architecture.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Agent Mode):

```
Implement the Approval Workflow module for the backend service.

Task 1 — Multi-Step Approval:
- 3+ role hierarchy: ba → business_owner → admin
- POST /api/approvals/{id}/approve
  - Require require_approver() RBAC
  - Record approver identity + timestamp
  - Advance workflow to next step
- POST /api/approvals/{id}/reject
  - Require require_approver() RBAC
  - Record rejection reason
  - Return to previous step or close workflow

Task 2 — HITL Trigger:
- When Validation Agent flags high-risk content:
  POST /api/approvals/hitl-trigger
  - Create approval record with type: "HUMAN_REVIEW"
  - Notify approvers (via notification service)
  - Block document from progressing until reviewed

Task 3 — Version Control:
- Every document change creates a new version in document_versions:
  {version_id, document_id, version_number, content_snapshot,
   changed_by, changed_at, change_reason}
- GET /api/documents/{id}/versions → list all versions
- GET /api/documents/{id}/versions/{version_id} → specific version

Task 4 — Audit Logging:
- Every approval action inserts to audit_logs:
  {action, entity_type: "approval", entity_id,
   user_id, details, created_at}
- Actions to log:
  APPROVAL_CREATED, APPROVAL_APPROVED,
  APPROVAL_REJECTED, HITL_TRIGGERED, VERSION_CREATED

Do NOT change architecture or docker-compose.yml.

Create:
- backend/app/routers/approvals.py
- backend/app/services/workflow.py
- backend/app/services/audit.py
```

---

### Step 3 — Expected Output Files

```
backend/app/
├── routers/
│   └── approvals.py            ← Approve/reject/HITL endpoints
└── services/
    ├── workflow.py             ← Multi-step workflow logic
    └── audit.py                ← Audit logging service
```

---

### Step 4 — Approval Workflow State Machine

```
[Document Ready]
      ↓
  PENDING_BA_REVIEW
      ↓ (ba approves)
  PENDING_OWNER_REVIEW
      ↓ (business_owner approves)
  PENDING_ADMIN_REVIEW
      ↓ (admin approves)
    APPROVED
      ↓ (any rejection)
    REJECTED
      ↓ (HITL triggered)
  HUMAN_REVIEW_REQUIRED
```

---

### Step 5 — Acceptance Tests (Must All Pass)

#### Test 1 — Approve a Document
```powershell
$ownerToken = "business_owner_access_token"
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/api/approvals/test-approval-id/approve" `
  -Headers @{ Authorization = "Bearer $ownerToken"; "Content-Type" = "application/json" } `
  -Body '{"comment":"Looks good"}'
# Expected: { status: "APPROVED" or next step status }
```

#### Test 2 — RBAC Block (BA cannot approve)
```powershell
$baToken = "ba_access_token"
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/api/approvals/test-id/approve" `
  -Headers @{ Authorization = "Bearer $baToken" }
# Expected: HTTP 403
```

#### Test 3 — Audit Log Recorded
- Check PostgreSQL `audit_logs` table
- Confirm APPROVAL_APPROVED action recorded with user_id + timestamp ✅

#### Test 4 — New Version Created
- Approve document → check `document_versions` table
- Confirm new version_number created ✅

#### Test 5 — List Versions
```powershell
Invoke-RestMethod -Method GET `
  -Uri "http://localhost:5000/api/documents/test-doc-id/versions" `
  -Headers @{ Authorization = "Bearer $ownerToken" }
# Expected: array of version objects
```

---

### Output

```
backend/app/routers/approvals.py    ← Approval endpoints
backend/app/services/workflow.py    ← Multi-step workflow logic
backend/app/services/audit.py       ← Audit logging
```

---

### Checklist

- [ ] Agent Mode activated before submitting prompt
- [ ] Both input files attached
- [ ] `POST /api/approvals/{id}/approve` endpoint created
- [ ] `POST /api/approvals/{id}/reject` endpoint created
- [ ] require_approver() RBAC applied to both endpoints
- [ ] Multi-step approval state machine implemented (3+ steps)
- [ ] HITL trigger endpoint created
- [ ] `POST /api/approvals/hitl-trigger` blocks document progression
- [ ] Every document change creates new version in `document_versions`
- [ ] `GET /api/documents/{id}/versions` endpoint created
- [ ] Every approval action logged to `audit_logs`
- [ ] All 5 audit action types logged correctly
- [ ] All 5 acceptance tests pass
- [ ] 🔒 All tests pass before proceeding to Stage 7H
