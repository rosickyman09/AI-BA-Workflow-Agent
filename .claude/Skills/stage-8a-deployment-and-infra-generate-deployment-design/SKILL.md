---
name: stage8a-deployment-design
description: Generates a complete deployment design document from the deployment plan and system architecture. Use this skill when the user wants to produce a deployment design, define Docker Compose structure, plan environment variables, design health checks, set up a rollback strategy, separate local vs production configs, define gateway routing rules, plan Docker volumes, or produce docs/05_deployment_plan.md. Trigger when the user mentions "deployment design", "deployment plan", "Docker Compose structure", "health checks", "rollback strategy", "local vs production", "reverse proxy routing", "container dependency order", "network segmentation", "image naming strategy", or wants to formalise how the project will be deployed before any infrastructure is provisioned.
---

## Stage 8A — Ask Mode: Deployment Design

### Purpose
Use Ask Mode to generate a detailed, implementation-ready deployment design from the deployment plan and system architecture. This document becomes the authoritative reference for all infrastructure provisioning, Docker configuration, and environment management.

> This is the design step. Infrastructure is not provisioned yet — this stage produces the plan that Stage 8B will execute.

---

### Prerequisites

- [ ] `docs/04_deployment_plan.txt` exists (Stage 2 complete)
- [ ] `docs/03_system_architecture.md` exists (Stage 5 complete)
- [ ] `docs/04_architecture_freeze.md` exists and is signed off (Stage 6 complete)
- [ ] `.copilot-instructions.md` is in place at project root

---

### Step 1 — Open Copilot in Ask Mode and Attach Both Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Use **Ask Mode**
3. Attach or reference both files:
   ```
   docs/04_deployment_plan.txt
   docs/03_system_architecture.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Ask Mode):

```
Based on the deployment plan document and system architecture,
generate the deployment design.

Please include:

1. Docker Compose structure
2. Environment variables
3. Service startup sequence
4. Health checks
5. Rollback strategy
6. Local development vs production setup
7. Dockerfiles required by each service
8. Reverse proxy / gateway routing rules
9. Docker volumes and persistent data
10. Container dependency order
11. Network segmentation
12. Image naming / build strategy

Create:
docs/05_deployment_plan.md
```

---

### Step 3 — Expected Output Structure

Copilot should produce `docs/05_deployment_plan.md` with the following sections:

```markdown
# Deployment Plan

## 1. Docker Compose Structure
- Full docker-compose.yml outline
- Service definitions (name, image or build path, ports, env_file, networks, volumes)
- Which services are built locally vs pulled from registry
- Example structure per service block

## 2. Environment Variables
| Variable | Service | Description | Required | Default |
|---|---|---|---|---|
| VAR_NAME | backend | purpose | Yes / No | (value or blank) |

- Variables grouped by service
- Secrets handling strategy (e.g. .env file, Docker secrets, external vault)
- .env.example file structure
- Variables that differ between local and production

## 3. Service Startup Sequence
| Order | Service | Depends On | Startup Check |
|---|---|---|---|
| 1 | database | — | port open / healthcheck passes |
| 2 | cache | — | port open |
| 3 | ai-service | database | healthcheck endpoint |
| 4 | backend | database, ai-service | healthcheck endpoint |
| 5 | gateway | backend, frontend | routing test |
| 6 | frontend | gateway | healthcheck endpoint |

- Rationale for each dependency
- Services that can start in parallel

## 4. Health Checks
| Service | Health Check Command | Interval | Timeout | Retries | Start Period |
|---|---|---|---|---|---|
| backend | curl -f http://localhost:PORT/health | 30s | 10s | 3 | 40s |
| database | pg_isready / equivalent | 10s | 5s | 5 | 30s |

- Health check endpoint definitions per service
- What each health check validates (port open, DB connected, model loaded, etc.)

## 5. Rollback Strategy
- How to roll back a failed deployment
- Image tagging strategy to support rollback (e.g. :latest vs :v1.2.3)
- Database migration rollback approach
- Volume data preservation during rollback
- Step-by-step rollback procedure

## 6. Local Development vs Production Setup
| Config Item | Local | Production |
|---|---|---|
| Port exposure | All ports open | Gateway only exposed externally |
| SSL | None | TLS termination at gateway |
| .env source | .env file | Secret manager / CI env injection |
| Volumes | Bind mounts for hot reload | Named volumes only |
| Image source | Built locally | Registry pull |
| Logging | Console output | Centralised logging service |

- docker-compose.override.yml for local-only config
- Production-specific environment hardening

## 7. Dockerfiles Required by Each Service
| Service | Dockerfile Path | Base Image | Build Stage | Notes |
|---|---|---|---|---|
| frontend | frontend/Dockerfile | node:xx-alpine | multi-stage | build → serve |
| backend | backend/Dockerfile | python:xx-slim | single-stage | |
| gateway | gateway/Dockerfile | nginx:alpine | single-stage | |
| ai-service | ai/Dockerfile | python:xx-slim | single-stage | GPU flag if needed |

- Multi-stage build rationale where used
- Image size optimisation notes
- .dockerignore requirements per service

## 8. Reverse Proxy / Gateway Routing Rules
| Path | Target Service | Internal Port | Strip Prefix? | Auth Required? |
|---|---|---|---|---|
| /api/ | backend | 8000 | Yes | Yes |
| /ai/ | ai-service | 8001 | Yes | Yes |
| / | frontend | 3000 | No | No |

- Gateway technology confirmed (e.g. Nginx, Traefik, Kong)
- Single-port vs multi-port decision (with reason)
- SSL termination point
- nginx.conf or equivalent routing config outline
- CORS and rate limiting at gateway level

## 9. Docker Volumes and Persistent Data
| Volume Name | Service | Mount Path | Data Type | Backup Strategy |
|---|---|---|---|---|
| db_data | database | /var/lib/postgresql/data | Relational DB | Daily snapshot |
| vector_data | ai-service | /app/vector_store | Vector embeddings | On re-ingestion |
| logs | backend | /app/logs | Application logs | Log rotation |

- Named vs anonymous volume decision
- Bind mounts for local development only
- Volume lifecycle (when to recreate vs preserve)

## 10. Container Dependency Order
- Full dependency graph (text-based)
- Which services can start in parallel
- Which services block others from starting
- Timeout thresholds before declaring a dependency failed

## 11. Network Segmentation
| Network Name | Services Attached | Purpose |
|---|---|---|
| frontend_net | frontend, gateway | Public-facing traffic |
| backend_net | backend, database, ai-service, gateway | Internal service traffic |
| ai_net | ai-service, backend | AI-specific isolation (optional) |

- Which services are on which network
- Services that bridge multiple networks (e.g. gateway)
- Services that must NOT be reachable from frontend network directly

## 12. Image Naming / Build Strategy
| Service | Local Image Name | Production Image Name | Tag Strategy |
|---|---|---|---|
| backend | project-backend | registry/project-backend | :latest (dev), :v1.x.x (prod) |

- Registry location (Docker Hub, GHCR, private registry)
- Tag naming convention (semantic version, git SHA, branch)
- CI/CD build trigger and push strategy
- Image scanning and validation before deploy
```

---

### Docker Completeness Checklist 🐳

Before marking `05_deployment_plan.md` complete, confirm all Docker sections are addressed:

| Section | Item | Included? |
|---|---|---|
| 1 | docker-compose.yml full structure outlined | ✅ |
| 3 | Startup sequence reflects frozen dependency order | ✅ |
| 4 | Every service has a health check defined | ✅ |
| 7 | Every containerized service has a named Dockerfile path | ✅ |
| 8 | Gateway routing rules cover all services and paths | ✅ |
| 9 | All persistent services have named volumes | ✅ |
| 10 | Dependency graph is explicit — no assumed startup order | ✅ |
| 11 | Network segmentation prevents frontend from accessing DB directly | ✅ |
| 12 | Image naming convention decided for both local and production | ✅ |

---

### Output

```
docs/
└── 05_deployment_plan.md    ← Full deployment design across 12 dimensions
```

This document is the direct input to Stage 8B, where the actual `docker-compose.yml`, Dockerfiles, gateway config, and environment files are generated.

---

### Checklist

- [ ] Ask Mode activated before submitting prompt
- [ ] Both input files attached (`04_deployment_plan.txt` + `03_system_architecture.md`)
- [ ] Full prompt used — all 12 sections requested
- [ ] `docs/05_deployment_plan.md` generated by Copilot
- [ ] All 12 sections present in the output
- [ ] Environment variables table complete for all services (Section 2)
- [ ] Service startup sequence matches frozen architecture dependency order (Section 3)
- [ ] Health check defined for every service (Section 4)
- [ ] Rollback procedure is step-by-step, not vague (Section 5)
- [ ] Local vs production differences are explicit — not implied (Section 6)
- [ ] Every containerized service has a Dockerfile path (Section 7) 🐳
- [ ] Gateway routing table covers all paths and services (Section 8) 🐳
- [ ] All persistent services have named volumes (Section 9) 🐳
- [ ] Network segmentation prevents direct frontend-to-database access (Section 11) 🐳
- [ ] Image naming convention confirmed for local and production (Section 12) 🐳
- [ ] Document reviewed before Stage 8B begins
