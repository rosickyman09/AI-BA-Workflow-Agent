---
name: stage9-testing-validation-refinement
description: Generates a test plan and operational runbook after the project is built. Use this skill when the user wants to produce a test plan, smoke test checklist, API validation checklist, deployment verification steps, troubleshooting guide, Docker container verification checklist, gateway routing verification, or persistence and volume verification. Trigger when the user mentions "test plan", "smoke test", "API validation", "deployment verification", "troubleshooting guide", "runbook", "container verification", "gateway verification", "volume verification", "validate deployment", or wants to produce docs/06_test_plan.md and docs/07_runbook.md after the project has been built in Stage 7 and deployed in Stage 8.
---

## Stage 9 — Testing, Validation, and Refinement

### Purpose
After the project is built and deployment files are generated, produce a structured test plan and operational runbook. These two documents ensure the system can be verified, troubleshot, and maintained reliably — by both the development team and future operators.

---

### Prerequisites

- [ ] Project code scaffold complete (Stage 7 done)
- [ ] Infrastructure files generated (Stage 8B done)
- [ ] `docker-compose.yml` and Dockerfiles exist and are runnable
- [ ] `docs/05_deployment_plan.md` exists (Stage 8A done)
- [ ] `docs/04_architecture_freeze.md` exists (Stage 6 done)
- [ ] `.copilot-instructions.md` is in place at project root

---

### Step 1 — Open Copilot Chat and Reference the Implemented Project

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Use **Ask Mode** or **Plan Mode**
3. Reference the implemented project and optionally attach:
   ```
   docs/04_architecture_freeze.md
   docs/05_deployment_plan.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat:

```
Based on the implemented project, generate:

1. Test plan
2. Smoke test checklist
3. API validation checklist
4. Deployment verification steps
5. Troubleshooting guide
6. Docker container verification checklist
7. Gateway routing verification
8. Persistence / volume verification

Create:
docs/06_test_plan.md
docs/07_runbook.md
```

---

### Step 3 — Expected Output: `docs/06_test_plan.md`

```markdown
# Test Plan

## 1. Test Plan Overview
- Test scope (what is being tested)
- Test environment (local / staging / production)
- Test types included (smoke, integration, API, manual)
- Pass/fail criteria
- Who runs each test and when

## 2. Smoke Test Checklist
Quick sanity checks to confirm the system is alive after deployment.

| # | Test | Expected Result | Pass? |
|---|---|---|---|
| 1 | All containers start without error | docker ps shows all services Up | |
| 2 | Frontend loads in browser | HTTP 200, UI renders | |
| 3 | Backend health endpoint returns OK | GET /health → 200 OK | |
| 4 | AI service responds to a test prompt | Valid response returned | |
| 5 | Database accepts a connection | No connection refused error | |
| 6 | Gateway routes / to frontend | Correct page served | |
| 7 | Gateway routes /api/ to backend | API response returned | |

## 3. API Validation Checklist
Verify each API endpoint behaves correctly.

| Endpoint | Method | Auth | Expected Status | Expected Response | Pass? |
|---|---|---|---|---|---|
| /health | GET | None | 200 | { status: ok } | |
| /api/[resource] | GET | Token | 200 | Data array | |
| /api/[resource] | POST | Token | 201 | Created object | |
| /api/[resource]/:id | PUT | Token | 200 | Updated object | |
| /api/[resource]/:id | DELETE | Token | 204 | Empty body | |
| /api/[invalid] | GET | None | 404 | Error message | |
| /api/[resource] | POST | No token | 401 | Unauthorised | |

(Expand with actual endpoints from the frozen architecture)

## 4. Deployment Verification Steps
Step-by-step verification that the deployment is complete and correct.

| Step | Command or Action | Expected Result | Pass? |
|---|---|---|---|
| 1. Start all services | docker compose up -d | No errors | |
| 2. Check running containers | docker ps | All services show Up (healthy) | |
| 3. Check logs for errors | docker compose logs | No ERROR or FATAL entries | |
| 4. Verify port exposure | curl http://localhost:[PORT] | Gateway responds | |
| 5. Verify internal routing | docker exec backend curl ai-service:PORT/health | 200 OK | |
| 6. Verify DB connection from backend | Check backend logs on startup | Connected message | |
| 7. Verify volume mounts | docker volume ls | All named volumes listed | |
| 8. Verify environment variables loaded | docker exec backend env | Expected vars present | |

## 5. Troubleshooting Guide

### Common Issues and Fixes

#### Container fails to start
- Check: `docker compose logs [service-name]`
- Likely causes: missing env var, port conflict, failed health check dependency
- Fix: check `.env` file, check port availability with `netstat -tuln`

#### Service unhealthy after start
- Check: `docker inspect [container-name] | grep -A 10 Health`
- Likely causes: health check command wrong, service not ready within start_period
- Fix: increase `start_period` in docker-compose.yml, verify health endpoint exists

#### Gateway returns 502 Bad Gateway
- Check: `docker compose logs gateway`
- Likely causes: upstream service not running, wrong internal port in nginx.conf
- Fix: verify upstream service is healthy, confirm port matches docker-compose.yml

#### Database connection refused
- Check: `docker compose logs database`
- Likely causes: DB container not yet healthy when backend started, wrong DB host in env
- Fix: confirm `depends_on: condition: service_healthy`, check DB_HOST env var value

#### AI service returns empty or error response
- Check: `docker compose logs ai-service`
- Likely causes: model not loaded, missing API key, vector store not initialised
- Fix: check AI service startup logs, verify API key env var, confirm vector volume mounted

#### Volume data not persisting
- Check: `docker volume inspect [volume-name]`
- Likely causes: anonymous volume used instead of named volume, volume not declared in compose
- Fix: ensure named volume declared in `volumes:` section and mounted correctly

## 6. Docker Container Verification Checklist 🐳

| Check | Command | Expected Result | Pass? |
|---|---|---|---|
| All containers running | `docker ps` | All services show Up | |
| All containers healthy | `docker ps` | Status shows (healthy) | |
| No unexpected containers | `docker ps` | Only planned services running | |
| Correct image used | `docker inspect [service] \| grep Image` | Expected image name/tag | |
| Correct ports exposed | `docker ps` | Only gateway port exposed externally | |
| Internal ports not exposed | `docker ps` | Backend/DB ports not in host column | |
| Named volumes exist | `docker volume ls` | All planned volumes listed | |
| Networks created | `docker network ls` | Project networks listed | |
| Env vars loaded | `docker exec [service] env` | All required vars present | |
| Non-root user running | `docker exec [service] whoami` | Not root | |

## 7. Gateway Routing Verification 🐳

| Route | Test Command | Expected Result | Pass? |
|---|---|---|---|
| / → frontend | `curl http://localhost:[PORT]/` | HTML response, 200 | |
| /api/ → backend | `curl http://localhost:[PORT]/api/health` | JSON response, 200 | |
| /ai/ → ai-service | `curl http://localhost:[PORT]/ai/health` | JSON response, 200 | |
| Unknown path → 404 | `curl http://localhost:[PORT]/unknown` | 404 error page | |
| Auth-required route without token | `curl http://localhost:[PORT]/api/[protected]` | 401 Unauthorised | |

- Verify gateway logs each request: `docker compose logs gateway -f`
- Verify no service is reachable by bypassing the gateway (internal ports not exposed)

## 8. Persistence / Volume Verification 🐳

| Verification Step | Action | Expected Result | Pass? |
|---|---|---|---|
| Data survives container restart | Write data → restart service → read data | Data still present | |
| Data survives full compose down/up | Write data → `docker compose down` → `up -d` → read | Data still present | |
| Volume not lost on image rebuild | Rebuild image → `up -d` → check data | Data still present | |
| Vector store persists after reingest | Ingest docs → restart ai-service → query | Results returned | |
| Database data persists | Insert record → restart DB container → query | Record returned | |
| Logs persist across restart | Generate logs → restart backend → check log volume | Logs still present | |
```

---

### Step 4 — Expected Output: `docs/07_runbook.md`

```markdown
# Runbook

## 1. Service Overview
| Service | Role | Container Name | Port | Health Endpoint |
|---|---|---|---|---|
| frontend | UI | project-frontend | internal:3000 | /health |
| backend | API | project-backend | internal:8000 | /health |
| gateway | Reverse proxy | project-gateway | external:80 | — |
| ai-service | AI orchestration | project-ai | internal:8001 | /health |
| database | Persistence | project-db | internal:5432 | pg_isready |

## 2. Day-to-Day Operations

### Start the system
```bash
cd project-root
./infra/scripts/start.sh
```

### Stop the system
```bash
./infra/scripts/stop.sh
```

### Restart a single service
```bash
docker compose restart [service-name]
```

### View live logs
```bash
./infra/scripts/logs.sh
# or for a single service:
docker compose logs -f [service-name]
```

### Full reset (warning: clears volumes)
```bash
./infra/scripts/reset.sh
```

## 3. Updating the System
1. Pull latest code
2. Rebuild images: `docker compose build`
3. Apply DB migrations (if any)
4. Restart services: `docker compose up -d`
5. Verify health: `docker ps`

## 4. Backup and Restore
- Database backup: `docker exec project-db pg_dump -U $DB_USER $DB_NAME > backup.sql`
- Database restore: `docker exec -i project-db psql -U $DB_USER $DB_NAME < backup.sql`
- Volume backup: `docker run --rm -v [volume]:/data -v $(pwd):/backup alpine tar czf /backup/[volume].tar.gz /data`

## 5. Escalation and Support
- First: check `docker compose logs [service]` for the failing service
- Second: check `docs/06_test_plan.md` troubleshooting section
- Third: review `docs/04_architecture_freeze.md` for expected behaviour
- Escalate: [team contact / issue tracker]
```

---

### Output

```
docs/
├── 06_test_plan.md     ← Test plan, checklists, API validation, Docker verification
└── 07_runbook.md       ← Operational runbook for day-to-day and incident management
```

---

### Checklist

- [ ] Both input documents attached if available (`04_architecture_freeze.md`, `05_deployment_plan.md`)
- [ ] Full prompt used — all 8 sections requested
- [ ] `docs/06_test_plan.md` generated by Copilot
- [ ] `docs/07_runbook.md` generated by Copilot
- [ ] Smoke test checklist covers all services (Section 2)
- [ ] API validation table includes auth, error, and 404 cases (Section 3)
- [ ] Deployment verification steps are commands — not vague descriptions (Section 4)
- [ ] Troubleshooting guide covers the 6 most common Docker failure scenarios (Section 5)
- [ ] Docker container verification checklist includes non-root user check (Section 6) 🐳
- [ ] Gateway routing verification tests every defined route (Section 7) 🐳
- [ ] Volume persistence verified across restart AND compose down/up AND rebuild (Section 8) 🐳
- [ ] Runbook includes all 5 day-to-day operation commands (07_runbook.md)
- [ ] Runbook includes backup and restore procedures (07_runbook.md)
- [ ] Both documents reviewed before project handover or production deployment
