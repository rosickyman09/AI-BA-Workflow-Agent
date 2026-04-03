---
name: stage8b-agent-mode-generate-infra-files
description: Generates all deployment and infrastructure files in Agent Mode from the completed deployment design. Use this skill when the user wants to create docker-compose.yml, Dockerfiles, .env.example, nginx.conf, gateway config, deployment scripts, health check configuration, or startup documentation. Trigger when the user mentions "generate infra files", "create docker-compose", "create Dockerfiles", "generate deployment files", "build infra", "create gateway config", "create nginx.conf", "generate .env.example", "deployment scripts", or wants to turn the deployment design document into real files. Always use Agent Mode — not Ask or Plan Mode — for this stage. Requires docs/05_deployment_plan.md to be complete before starting.
---

## Stage 8B — Agent Mode: Generate Infrastructure Files

### Purpose
Use Agent Mode to generate all real deployment and infrastructure files from the completed deployment design. This stage produces the actual files — not documentation — that make the project runnable.

> ⚠️ **Use Agent Mode only.** Ask Mode is for design (Stage 8A). Agent Mode is for execution (Stage 8B). Do not mix them.

---

### Why the Split Between 8A and 8B

| Stage | Mode | Purpose |
|---|---|---|
| 8A | Ask Mode | Think through and design the deployment — produce `05_deployment_plan.md` |
| 8B | Agent Mode | Execute the design — generate the actual files from `05_deployment_plan.md` |

Designing and generating in the same prompt leads to inconsistent output. Ask Mode reasons well but doesn't reliably create files. Agent Mode creates files reliably but needs a clear, pre-agreed design to follow.

---

### Prerequisites

- [ ] `docs/05_deployment_plan.md` is complete and reviewed (Stage 8A complete)
- [ ] `docs/04_architecture_freeze.md` is signed off (Stage 6 complete)
- [ ] `docs/03_system_architecture.md` exists (Stage 5 complete)
- [ ] All service folders exist (`frontend/`, `backend/`, `gateway/`, `infra/`)
- [ ] `.copilot-instructions.md` is in place at project root

---

### Step 1 — Switch to Agent Mode and Attach the Input File

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach the deployment design document:
   ```
   docs/05_deployment_plan.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Agent Mode):

```
Based on docs/05_deployment_plan.md, generate the deployment files.

Please create:
- docker-compose.yml
- .env.example
- frontend/Dockerfile
- backend/Dockerfile
- gateway/Dockerfile (if gateway is required)
- gateway/nginx.conf (if single-port architecture)
- deployment scripts
- health check configuration
- startup documentation
```

---

### Step 3 — Expected Output Files

Agent Mode must produce all of the following. Check each file exists after the run:

#### Core Deployment Files 🐳

```
project-root/
├── docker-compose.yml              ← Full service orchestration
├── .env.example                    ← All environment variables documented
```

#### Service Dockerfiles 🐳

```
frontend/
└── Dockerfile                      ← Frontend container build

backend/
└── Dockerfile                      ← Backend container build

gateway/
├── Dockerfile                      ← Gateway container build (if required)
└── nginx.conf                      ← Reverse proxy routing (if single-port)
```

#### Deployment Scripts

```
infra/
├── scripts/
│   ├── start.sh                    ← Start all services
│   ├── stop.sh                     ← Stop all services
│   ├── restart.sh                  ← Restart all services
│   ├── logs.sh                     ← Tail logs across services
│   └── reset.sh                    ← Stop, remove volumes, restart clean
```

#### Health Check Configuration

```
infra/
└── healthchecks/
    └── healthcheck-config.yml      ← Health check definitions per service
```

#### Startup Documentation

```
docs/
└── 06_startup_guide.md             ← Step-by-step instructions to run the project
```

---

### Step 4 — File Content Requirements

#### `docker-compose.yml` must include:
- All services from the frozen architecture
- `build` or `image` per service (matching the deployment plan)
- Port mappings — internal only for non-gateway services
- `env_file: .env` for all services
- `depends_on` with `condition: service_healthy` where health checks exist
- Named volumes for all persistent services
- Network definitions — `frontend_net` and `backend_net` (or as designed)
- `restart: unless-stopped` for production-grade resilience

#### `.env.example` must include:
- Every environment variable used across all services
- Inline comments explaining each variable's purpose
- Placeholder values (not real secrets)
- Clear section headers per service

#### Each `Dockerfile` must include:
- Correct base image per service (from deployment plan Section 7)
- Multi-stage build where applicable (e.g. frontend build → serve)
- `.dockerignore` respected (node_modules, __pycache__, .env, etc.)
- Non-root user defined for security
- `HEALTHCHECK` instruction included

#### `gateway/nginx.conf` must include (if single-port):
- Upstream blocks per backend service
- Location blocks routing paths to correct upstreams
- Proxy headers (`X-Real-IP`, `X-Forwarded-For`, etc.)
- Error page definitions
- Gzip compression enabled

#### Deployment scripts must be executable:
- `start.sh` → `docker compose up -d --build`
- `stop.sh` → `docker compose down`
- `restart.sh` → `docker compose restart`
- `logs.sh` → `docker compose logs -f`
- `reset.sh` → `docker compose down -v && docker compose up -d --build`

#### `docs/06_startup_guide.md` must include:
- Prerequisites (Docker version, OS requirements)
- First-time setup steps (clone, copy .env, fill in values)
- How to start the project locally
- How to verify all services are healthy
- How to access frontend, backend, and any admin UIs
- Common error messages and fixes
- How to stop and clean up

---

### Docker Rules for Agent Mode 🐳

Agent Mode must follow all rules from `.copilot-instructions.md` and the frozen architecture. Specifically:

| Rule | Requirement |
|---|---|
| Service names | Must match exactly across `docker-compose.yml`, Dockerfiles, nginx.conf, and scripts |
| Port exposure | Only the gateway port should be exposed externally — all others internal only |
| Volumes | Every persistent service must have a named volume — no anonymous volumes |
| Health checks | Every service must have a HEALTHCHECK in its Dockerfile and `healthcheck:` in docker-compose.yml |
| Networks | Services must be on the correct network — frontend must not reach the database directly |
| Startup order | `depends_on` must reflect the startup sequence from the deployment plan |
| Do not deviate | If a conflict is found between the prompt and the deployment plan, stop and flag it — do not resolve silently |

---

### Output Summary

```
project-root/
├── docker-compose.yml
├── .env.example
├── frontend/
│   └── Dockerfile
├── backend/
│   └── Dockerfile
├── gateway/
│   ├── Dockerfile
│   └── nginx.conf
├── infra/
│   ├── scripts/
│   │   ├── start.sh
│   │   ├── stop.sh
│   │   ├── restart.sh
│   │   ├── logs.sh
│   │   └── reset.sh
│   └── healthchecks/
│       └── healthcheck-config.yml
└── docs/
    └── 06_startup_guide.md
```

---

### Checklist

- [ ] Agent Mode activated — not Ask or Plan Mode
- [ ] `docs/05_deployment_plan.md` attached as the input
- [ ] Full prompt used — all 9 output files requested
- [ ] `docker-compose.yml` created with all services, ports, volumes, networks, depends_on 🐳
- [ ] `.env.example` created with all variables documented and commented
- [ ] `frontend/Dockerfile` created with HEALTHCHECK instruction 🐳
- [ ] `backend/Dockerfile` created with HEALTHCHECK instruction 🐳
- [ ] `gateway/Dockerfile` created (if gateway required) 🐳
- [ ] `gateway/nginx.conf` created with routing rules (if single-port) 🐳
- [ ] All deployment scripts created and marked executable (`chmod +x`) 🐳
- [ ] Health check config file created in `infra/healthchecks/`
- [ ] `docs/06_startup_guide.md` created with first-time setup steps
- [ ] Service names consistent across all generated files 🐳
- [ ] Only gateway port exposed externally — all others internal 🐳
- [ ] All persistent services have named volumes in docker-compose.yml 🐳
- [ ] `depends_on` startup order matches deployment plan Section 3 🐳
- [ ] No architectural deviations made silently — all flagged and reviewed
