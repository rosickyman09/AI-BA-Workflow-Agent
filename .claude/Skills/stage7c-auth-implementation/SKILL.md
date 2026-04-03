---
name: stage7c-auth-implementation
description: Implements real database authentication and RBAC for the project. Use this skill when the user wants to replace mock login with real PostgreSQL authentication, implement bcrypt password verification, add JWT with real user data, create role-based access control (RBAC) middleware, add audit logging for login events, or wire up auth_service to a real database. Trigger when the user mentions "real auth", "real login", "RBAC", "bcrypt", "JWT with roles", "replace mock auth", "auth implementation", "auth middleware", "role-based access", or wants to implement Stage 7C after the project scaffold is built.
---

## Stage 7C — Agent Mode: Real Auth Implementation

### Purpose
Replace any mock authentication with a real database-backed login system. This stage implements bcrypt password verification, JWT generation with real user data, RBAC middleware for role-based endpoint protection, and audit logging — using PostgreSQL as the source of truth.

> ⚠️ Do NOT change the architecture, docker-compose.yml, database schema, or port assignments during this stage. Implementation only — no structural changes.

---

### Why This Stage Exists

At the end of Stage 7 (initial build), auth_service typically uses mock login — accepting any credentials and returning a generic JWT. This is intentional for scaffolding. Stage 7C upgrades it to production-grade authentication:

- Login validates against real `users` table in PostgreSQL
- Passwords verified with bcrypt (not plain-text comparison)
- JWT contains real user data: `{user_id, email, role, projects}`
- Every API endpoint enforces RBAC based on role
- Every login attempt is recorded in `audit_logs`

---

### Prerequisites

- [ ] `auth_service/app/main.py` exists (Stage 7 scaffold complete)
- [ ] `infra/migrations/001_initial_schema.sql` exists (DB schema with `users` table)
- [ ] `docs/03_system_architecture.md` exists (RBAC section defined)
- [ ] `docs/04_architecture_freeze.md` is signed off (Stage 6 complete)
- [ ] PostgreSQL container is running and seeded with test users
- [ ] `.copilot-instructions.md` is in place at project root

---

### Step 1 — Switch to Agent Mode and Attach Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach all three input files:
   ```
   auth_service/app/main.py
   infra/migrations/001_initial_schema.sql
   docs/03_system_architecture.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Agent Mode):

```
Implement real DB authentication for auth_service.

Task 1 — Real DB Authentication (auth_service/app/main.py):
- Connect to PostgreSQL using environment variables:
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
- On POST /auth/login:
  1. Query users table: SELECT * FROM users WHERE email = ?
  2. Verify password using bcrypt (passlib library)
  3. If invalid → return HTTP 401 {"detail": "Invalid credentials"}
  4. If valid → return JWT containing:
     {user_id, email, role, full_name, projects}
- Use psycopg2 or sqlalchemy for DB connection

Task 2 — RBAC Middleware (backend/app/main.py or middleware):
- Create dependency function get_current_user(token)
  that decodes JWT and returns user info
- Create role-based dependencies:
  - require_admin() → only admin role
  - require_approver() → business_owner or legal or admin
  - require_ba() → ba, pm, tech_lead, admin
  - require_readonly() → all roles (viewer/it included)
- Apply to endpoints:
  - POST /api/approvals/{id}/approve → require_approver()
  - POST /api/approvals/{id}/reject → require_approver()
  - POST /api/documents/upload → require_ba()
  - GET /api/documents/{id} → require_readonly()

Task 3 — Audit Logging:
- On every login attempt, insert into audit_logs:
  {action: "LOGIN_SUCCESS" or "LOGIN_FAILED",
   user_id: (if found),
   entity_type: "auth",
   created_at: now()}

Constraints:
- Do NOT change docker-compose.yml
- Do NOT change database schema
- Do NOT change port assignments
- Keep existing /health and /auth/health endpoints
```

---

### Step 3 — Expected Output Files

Agent Mode must produce or modify:

```
auth_service/app/
└── main.py                     ← Updated with real DB login + bcrypt + JWT

backend/
├── app/
│   ├── middleware/
│   │   └── auth.py             ← RBAC middleware with role dependencies
│   └── main.py                 ← Updated to use RBAC dependencies on endpoints
```

---

### Step 4 — Test Accounts (Pre-seeded in DB)

| Email | Password | Role |
|---|---|---|
| admin@ai-ba.local | password123 | admin |
| ba1@ai-ba.local | password123 | ba |
| owner@ai-ba.local | password123 | business_owner |

---

### Step 5 — Acceptance Tests (Must All Pass)

Run these after implementation to confirm the stage is complete:

#### Test 1 — Valid Login
```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5001/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"admin@ai-ba.local","password":"password123"}'
# Expected: HTTP 200 + access_token in response
```

#### Test 2 — Invalid Password
```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5001/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"admin@ai-ba.local","password":"wrongpassword"}'
# Expected: HTTP 401
```

#### Test 3 — RBAC Block (IT user cannot approve)
```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/api/approvals/test-id/approve" `
  -Headers @{ Authorization = "Bearer [IT_USER_TOKEN]" }
# Expected: HTTP 403
```

#### Test 4 — RBAC Allow (business_owner can approve)
```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/api/approvals/test-id/approve" `
  -Headers @{ Authorization = "Bearer [OWNER_TOKEN]" }
# Expected: HTTP 200
```

#### Test 5 — Profile Endpoint
```powershell
Invoke-RestMethod -Method GET `
  -Uri "http://localhost:5001/auth/me" `
  -Headers @{ Authorization = "Bearer [TOKEN]" }
# Expected: real user data from DB (not mock)
```

---

### RBAC Role Reference

| Role | Can Approve | Can Upload Docs | Can View Docs | Admin Functions |
|---|---|---|---|---|
| admin | ✅ | ✅ | ✅ | ✅ |
| business_owner | ✅ | ❌ | ✅ | ❌ |
| ba | ❌ | ✅ | ✅ | ❌ |
| it | ❌ | ❌ | ✅ | ❌ |

---

### Output

```
auth_service/app/main.py         ← Real DB login, bcrypt, JWT with role + projects
backend/middleware/auth.py       ← RBAC middleware with 4 role dependencies
backend/app/main.py              ← Endpoints protected by RBAC
```

---

### Checklist

- [ ] Agent Mode activated before submitting prompt
- [ ] All three input files attached
- [ ] `auth_service/app/main.py` updated with real PostgreSQL connection
- [ ] bcrypt password verification implemented (not plain-text)
- [ ] JWT now contains: `user_id`, `email`, `role`, `full_name`, `projects`
- [ ] HTTP 401 returned for invalid credentials (not 200)
- [ ] `backend/middleware/auth.py` created with all 4 role dependencies
- [ ] RBAC applied to approval endpoints (require_approver)
- [ ] RBAC applied to upload endpoint (require_ba)
- [ ] RBAC applied to document view endpoint (require_readonly)
- [ ] Audit logging inserts to `audit_logs` on every login attempt
- [ ] All 5 acceptance tests pass
- [ ] `/health` and `/auth/health` endpoints still working
- [ ] docker-compose.yml unchanged
- [ ] Database schema unchanged
- [ ] Port assignments unchanged
- [ ] 🔒 All tests pass before proceeding to Stage 7D
