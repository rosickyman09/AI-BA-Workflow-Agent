---
name: stage8b-railway-db-deploy
description: Deploys the database layer to Railway including PostgreSQL, Qdrant vector store, and Redis. Use this skill when the user wants to deploy PostgreSQL to Railway, run database migrations on Railway, deploy Qdrant to Railway, deploy Redis to Railway, or verify all database services are healthy before deploying backend services. Trigger when the user mentions "Railway database", "deploy PostgreSQL Railway", "Railway migrations", "Railway Qdrant", "Railway Redis", "database layer deployment", or wants to implement Stage 8B (Railway DB) after Railway setup is complete.
---

## Stage 8B — Agent Mode + Manual: Railway DB Deployment

### Purpose
Deploy the complete database layer to Railway: managed PostgreSQL (with migrations and seed data), Qdrant vector store, and Redis cache. All three must be healthy before any backend services are deployed.

> ⚠️ Deploy in order: PostgreSQL first → run migrations → Qdrant → Redis. Do NOT deploy backend before all DB services are healthy.

---

### Prerequisites

- [ ] Stage 8A complete — Railway project setup and all env vars set
- [ ] `docs/05_deployment_plan.md` exists
- [ ] Migration files exist:
  - `infra/migrations/001_initial_schema.sql`
  - `infra/migrations/002_add_indexes.sql`
  - `infra/migrations/003_seed_data.sql`
- [ ] Railway project connected to GitHub

---

### Step 1 — Agent Mode: Get Deployment Instructions

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach:
   ```
   docs/05_deployment_plan.md
   ```
4. Use the prompt in Step 2 below

---

### Step 2 — Copilot Prompt

```
Deploy the database layer to Railway.

Task 1 — PostgreSQL (Railway Managed):
- Add Railway PostgreSQL plugin to project
- Get DATABASE_URL from Railway dashboard
- Update all services to use DATABASE_URL
- Run migrations in order:
  001_initial_schema.sql
  002_add_indexes.sql
  003_seed_data.sql
- Verify: 11 tables created, seed data present

Task 2 — Qdrant:
- Deploy Qdrant using Docker image: qdrant/qdrant:v1.13.6
- Set Railway service name: qdrant
- Set volume for persistence: /qdrant/storage
- Verify: GET /health returns {"status":"ok"}

Task 3 — Redis:
- Add Railway Redis plugin to project
- Get REDIS_URL from Railway dashboard
- Update rag_service and backend to use REDIS_URL
- Verify: PING returns PONG

Provide step-by-step Railway dashboard instructions.
Do NOT deploy backend services yet.
```

---

### Step 3 — Manual: Deploy PostgreSQL on Railway

1. In Railway dashboard → **New Service** → **Database** → **PostgreSQL**
2. Wait for PostgreSQL to deploy (green status)
3. Click PostgreSQL service → **Connect** tab
4. Copy `DATABASE_URL`
5. Set `DATABASE_URL` in all service Variables that need DB access

---

### Step 4 — Manual: Run Migrations

After PostgreSQL is healthy, run migrations via Railway shell or local psql:

```bash
# Option A: Railway CLI
railway run psql $DATABASE_URL -f infra/migrations/001_initial_schema.sql
railway run psql $DATABASE_URL -f infra/migrations/002_add_indexes.sql
railway run psql $DATABASE_URL -f infra/migrations/003_seed_data.sql

# Option B: Local psql pointing to Railway DB
psql $DATABASE_URL -f infra/migrations/001_initial_schema.sql
psql $DATABASE_URL -f infra/migrations/002_add_indexes.sql
psql $DATABASE_URL -f infra/migrations/003_seed_data.sql
```

Verify tables created:
```bash
psql $DATABASE_URL -c "\dt"
# Expected: 11 tables listed
```

---

### Step 5 — Manual: Deploy Qdrant on Railway

1. In Railway dashboard → **New Service** → **Docker Image**
2. Image: `qdrant/qdrant:v1.13.6`
3. Service name: `qdrant`
4. Add volume: `/qdrant/storage`
5. Wait for green status
6. Verify health:
   ```bash
   curl https://[qdrant-railway-url]/health
   # Expected: {"status":"ok"}
   ```

---

### Step 6 — Acceptance Tests (Must All Pass)

#### Test 1 — PostgreSQL Healthy
```bash
railway run psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"
# Expected: 4 (seeded test users)
```

#### Test 2 — Migrations Applied
```bash
railway run psql $DATABASE_URL -c "\dt"
# Expected: 11 tables
```

#### Test 3 — Qdrant Healthy
```bash
curl https://[qdrant-url]/health
# Expected: {"status":"ok"}
```

#### Test 4 — Redis Healthy
```bash
railway run redis-cli -u $REDIS_URL PING
# Expected: PONG
```

---

### Completion Checklist

| Item | Check |
|---|---|
| PostgreSQL service deployed on Railway | ☐ |
| DATABASE_URL set in all service variables | ☐ |
| Migration 001 applied | ☐ |
| Migration 002 applied | ☐ |
| Migration 003 (seed data) applied | ☐ |
| 11 tables confirmed | ☐ |
| 4 seed users confirmed | ☐ |
| Qdrant deployed (v1.13.6) | ☐ |
| Qdrant /health returns ok | ☐ |
| Qdrant volume mounted | ☐ |
| Redis deployed | ☐ |
| REDIS_URL set in service variables | ☐ |
| Redis PING returns PONG | ☐ |

---

### Output

```
Railway PostgreSQL ✅  (11 tables, seed data)
Railway Qdrant ✅      (v1.13.6, healthy)
Railway Redis ✅       (healthy)
Ready for Stage 8C (Backend deployment) ✅
```

---

### Checklist

- [ ] Agent Mode used for deployment instructions
- [ ] `docs/05_deployment_plan.md` attached
- [ ] PostgreSQL deployed and healthy
- [ ] DATABASE_URL copied and set in all relevant Railway service variables
- [ ] All 3 migration files run in order (001, 002, 003)
- [ ] 11 tables confirmed in PostgreSQL
- [ ] Seed data confirmed (4 users)
- [ ] Qdrant deployed with pinned version v1.13.6
- [ ] Qdrant volume configured for persistence
- [ ] Redis deployed and healthy
- [ ] REDIS_URL set in service variables
- [ ] All 4 acceptance tests pass
- [ ] 🔒 All DB services healthy before proceeding to Stage 8C!
