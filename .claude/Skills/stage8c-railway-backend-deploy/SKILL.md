---
name: stage8c-railway-backend-deploy
description: Deploys all three backend services to Railway in the correct order. Use this skill when the user wants to deploy auth_service, backend API, or rag_service to Railway, configure Railway build settings for Python services, verify backend health endpoints on Railway, or deploy services in the correct dependency order. Trigger when the user mentions "deploy backend Railway", "auth_service Railway", "backend service Railway", "rag_service Railway", "Railway Python service", "backend deployment order", or wants to implement Stage 8C after the database layer is healthy on Railway.
---

## Stage 8C — Agent Mode: Railway Backend Deployment

### Purpose
Deploy all three backend services to Railway in strict dependency order: auth_service first, then backend API, then rag_service. Each service must be verified healthy before the next one is deployed.

> ⚠️ Strict deployment order: auth_service → backend → rag_service. Do NOT deploy the next service until the current one shows healthy.

---

### Prerequisites

- [ ] Stage 8B complete — PostgreSQL, Qdrant, Redis all healthy on Railway
- [ ] `docs/05_deployment_plan.md` exists
- [ ] All environment variables set in Railway (from Stage 8A)
- [ ] DATABASE_URL, REDIS_URL, QDRANT_URL all available in Railway
- [ ] Code committed and pushed to GitHub

---

### Step 1 — Switch to Agent Mode and Attach Input File

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach:
   ```
   docs/05_deployment_plan.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

```
Deploy the three backend services to Railway in order.

Deployment Order (MUST follow — do not change):
1. auth_service (port 5001)
2. backend (port 5000)
3. rag_service (port 5002)

For each service:

auth_service:
- Root directory: auth_service/
- Build command: pip install -r requirements.txt
- Start command: uvicorn app.main:app --host 0.0.0.0 --port 5001
- Required env vars: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, JWT_SECRET
- Health check: GET /auth/health → {"status":"healthy"}

backend:
- Root directory: backend/
- Build command: pip install -r requirements.txt
- Start command: uvicorn app.main:app --host 0.0.0.0 --port 5000
- Required env vars: DATABASE_URL, JWT_SECRET, AUTH_SERVICE_URL, RAG_SERVICE_URL
- Health check: GET /health → {"status":"healthy"}

rag_service:
- Root directory: rag_service/
- Build command: pip install -r requirements.txt
- Start command: uvicorn app.main:app --host 0.0.0.0 --port 5002
- Required env vars: DATABASE_URL, QDRANT_URL, QDRANT_API_KEY,
  REDIS_URL, OPENROUTER_API_KEY, DEEPSEEK_API_KEY, ELEVENLABS_API_KEY
- Health check: GET /rag/health → {"status":"healthy"}

Verify each health endpoint BEFORE deploying next service.
Provide Railway dashboard instructions for each service.
```

---

### Step 3 — Manual: Deploy Each Service on Railway

For each service, in Railway dashboard:

1. **New Service** → **GitHub Repo**
2. Select the repository
3. Set **Root Directory** (e.g. `auth_service`)
4. Set **Build Command** and **Start Command**
5. Add all required environment variables
6. Click **Deploy**
7. Wait for green status → verify health endpoint

---

### Step 4 — Service Configuration Reference

| Service | Root Dir | Port | Start Command |
|---|---|---|---|
| auth_service | `auth_service/` | 5001 | `uvicorn app.main:app --host 0.0.0.0 --port 5001` |
| backend | `backend/` | 5000 | `uvicorn app.main:app --host 0.0.0.0 --port 5000` |
| rag_service | `rag_service/` | 5002 | `uvicorn app.main:app --host 0.0.0.0 --port 5002` |

---

### Step 5 — Acceptance Tests (Must All Pass)

#### Test 1 — auth_service Healthy
```bash
curl https://[auth-railway-url]/auth/health
# Expected: {"status":"healthy"}
```

#### Test 2 — auth_service Login Works
```bash
curl -X POST https://[auth-railway-url]/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@ai-ba.local","password":"password123"}'
# Expected: access_token in response
```

#### Test 3 — backend Healthy
```bash
curl https://[backend-railway-url]/health
# Expected: {"status":"healthy"}
```

#### Test 4 — rag_service Healthy
```bash
curl https://[rag-railway-url]/rag/health
# Expected: {"status":"healthy"}
```

---

### Deployment Order Gate Rules

| Gate | Condition | Action |
|---|---|---|
| Gate 1 | auth_service /auth/health → healthy | Deploy backend |
| Gate 2 | backend /health → healthy | Deploy rag_service |
| Gate 3 | rag_service /rag/health → healthy | Proceed to Stage 8D |

---

### Output

```
Railway auth_service ✅   (port 5001, healthy)
Railway backend ✅         (port 5000, healthy)
Railway rag_service ✅     (port 5002, healthy)
Railway URLs saved for Stage 8D ✅
```

---

### Checklist

- [ ] Agent Mode used for deployment instructions
- [ ] `docs/05_deployment_plan.md` attached
- [ ] auth_service deployed FIRST
- [ ] auth_service /auth/health returns healthy ✅
- [ ] auth_service login test passes ✅
- [ ] backend deployed SECOND (after auth_service healthy)
- [ ] backend /health returns healthy ✅
- [ ] AUTH_SERVICE_URL set to Railway auth_service URL
- [ ] rag_service deployed THIRD (after backend healthy)
- [ ] rag_service /rag/health returns healthy ✅
- [ ] All 4 acceptance tests pass
- [ ] Railway URLs for all 3 services saved
- [ ] 🔒 All 3 services healthy before proceeding to Stage 8D!
