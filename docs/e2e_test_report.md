Criterion 6 — Approval workflow:
Deliberately simplified to 2-step
(business_owner → admin) as seed data
does not include legal role.
This is an accepted design decision.

## Pre-Railway 4-Case Checklist

Use this checklist as a quick go/no-go before Railway deployment.

### Case 1: End-to-End Document Processing

Goal: Validate upload -> processing -> searchable result.

Steps:
1. Login as `ba1@ai-ba.local` with password `password123`.
2. Upload `test_doc.txt` via UI (`/documents`) or API (`POST /api/documents/upload`).
3. Poll `GET /api/documents/{doc_id}/status` until terminal status.
4. Run `POST /rag/search` with query `authentication` and project_id `660e8400-e29b-41d4-a716-446655440000`.

Expected:
- Upload returns HTTP 200 with `document_id`.
- Final status is `COMPLETED`.
- Search returns HTTP 200 with at least one result.

Result:
- [ ] PASS
- [ ] FAIL
Notes:

### Case 2: RBAC Security Matrix

Goal: Validate permission boundaries by role.

Steps:
1. Login as `admin@ai-ba.local`, `ba1@ai-ba.local`, `owner@ai-ba.local`, `it@ai-ba.local` (all with `password123`).
2. Try upload as IT.
3. Upload as BA and capture workflow_id.
4. Approve as owner using captured workflow_id.
5. Attempt approve as BA on same/new workflow.

Expected:
- All logins succeed with correct role claim.
- IT upload returns HTTP 403.
- BA upload returns HTTP 200.
- Owner approve returns HTTP 200.
- BA approve returns HTTP 403.

Result:
- [ ] PASS
- [ ] FAIL
Notes:

### Case 3: Workflow Timing + Persisted Summarization

Goal: Validate runtime SLA and DB quality.

Steps:
1. Call `POST /rag/workflow/execute` with:
	- document_id: `df3da7b3-67e6-4cb4-937a-da4650a724b0`
	- project_id: `660e8400-e29b-41d4-a716-446655440000`
	- content: `Meeting: Team agreed on JWT auth and RBAC implementation.`
2. Measure wall-clock time.
3. Query:
	- `SELECT agent_name, state_data FROM agent_state WHERE agent_name ILIKE '%summar%' ORDER BY created_at DESC LIMIT 1;`

Expected:
- HTTP 200 response from workflow execute.
- Total time < 120000 ms.
- `state_data` contains `markdown` and `document`.

Result:
- [ ] PASS
- [ ] FAIL
Notes:

### Case 4: Restart Resilience

Goal: Validate core flows survive service restarts.

Steps:
1. Restart rag_service and verify `GET /rag/health`.
2. Restart backend + auth_service and verify health endpoints.
3. Re-run one admin upload (`POST /api/documents/upload`) and wait for `COMPLETED`.
4. Re-run `POST /rag/search` for `authentication`.
5. Verify unauthenticated `GET /api/documents` is rejected.

Expected:
- Health endpoints report healthy.
- Upload still succeeds and reaches `COMPLETED`.
- Search returns HTTP 200.
- Unauthenticated documents list is blocked (401/403).

Result:
- [ ] PASS
- [ ] FAIL
Notes:
