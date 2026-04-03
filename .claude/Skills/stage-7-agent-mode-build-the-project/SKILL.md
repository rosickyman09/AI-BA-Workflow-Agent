---
name: stage7-agent-mode-build-project
description: Builds the full project in Agent Mode using the frozen architecture as the single source of truth. Use this skill when the user is ready to generate code, scaffold the project structure, create Dockerfiles, set up backend services, build frontend structure, create database schemas, implement AI agent modules, configure a gateway, or prepare the infra folder. Trigger when the user mentions "build the project", "start coding", "Agent Mode build", "create project structure", "generate code", "create Dockerfiles", "scaffold backend", "scaffold frontend", "create AI modules", or wants to begin implementation after architecture is frozen. Always attach the three frozen architecture documents before starting. Do not allow architecture changes during this stage unless explicitly instructed.
---

## Stage 7 — Agent Mode: Build the Project

### Purpose
Use Agent Mode to build the project step by step, strictly following the frozen architecture. All folders, services, configs, Dockerfiles, and code must align with `docs/04_architecture_freeze.md`. No architectural decisions should be made or changed during this stage.

> ⚠️ Agent Mode must not deviate from the frozen architecture. If a conflict is detected, stop and flag it — do not silently change the design.

---

### Prerequisites

- [ ] `docs/02b_agent_skill_matrix.md` exists (Stage 4B complete)
- [ ] `docs/03_system_architecture.md` exists (Stage 5 complete)
- [ ] `docs/04_architecture_freeze.md` exists and is signed off (Stage 6 complete)
- [ ] `.copilot-instructions.md` is in place at project root
- [ ] Tech stack confirmed and ready to fill into the prompt

---

### Step 1 — Switch to Agent Mode

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach all three input documents:
   ```
   docs/02b_agent_skill_matrix.md
   docs/03_system_architecture.md
   docs/04_architecture_freeze.md
   ```
4. Fill in the tech stack fields in the prompt below before submitting

---

### Step 2 — Copilot Prompt

Fill in your tech stack, then copy and paste the full prompt into Copilot Chat (Agent Mode):

```
Build the project based on the approved architecture.

Create the project structure and code step by step.
Do not change the architecture unless explicitly stated.

Tech stack:       ____________________
Frontend:         ____________________
Backend:          ____________________
Database:         ____________________
AI orchestration: ____________________
Vector DB:        ____________________

Please:
1. Create folders first
2. Create base config files
3. Create backend services
4. Create frontend structure
5. Create database schema / migrations
6. Create AI agent modules
7. Add basic logging and error handling
8. Explain what you created after each step
9. Create Dockerfiles for all containerized services
10. Create gateway config if gateway is required
11. Prepare Docker-related folder structure under /infra or service folders
12. Keep all service names consistent with the planned docker-compose design
```

---

### Step 3 — Build Order

Agent Mode should follow this sequence. If it deviates, redirect it:

#### Phase 1 — Project Skeleton
```
1. Create top-level folder structure
   (frontend/, backend/, gateway/, infra/, docs/, prompts/)
2. Create .env.example at project root
3. Create docker-compose.yml skeleton (service names only, no full config yet)
```

#### Phase 2 — Configuration Files
```
4. Backend base config (settings, environment loader)
5. Frontend base config (framework config, env setup)
6. Logging config (shared log format, output target)
```

#### Phase 3 — Backend Services
```
7. Main application entry point
8. Route definitions (aligned with frozen API contracts)
9. Service layer modules (one per agent / functional module)
10. Database connection setup
11. Database schema / migration files
```

#### Phase 4 — Frontend Structure
```
12. Page / component scaffold
13. API client / service layer for backend calls
14. State management setup (if applicable)
```

#### Phase 5 — AI Agent Modules
```
15. Agent base class or orchestration entry point
16. Individual agent modules (one per agent in skill matrix)
17. RAG pipeline setup (ingestion, embedding, retrieval)
18. Tool definitions per agent
19. Memory setup (short-term and long-term)
```

#### Phase 6 — Logging and Error Handling
```
20. Structured logging across all services
21. Global error handler per service
22. Fallback logic per agent (from workflow design)
```

#### Phase 7 — Docker and Infrastructure 🐳
```
23. backend/Dockerfile
24. frontend/Dockerfile
25. gateway/Dockerfile (if gateway required)
26. gateway/nginx.conf (if single-port architecture)
27. infra/ folder with any supporting config
28. Complete docker-compose.yml
    - Service names matching frozen architecture
    - Port mappings (internal and external)
    - Volumes for persistent services
    - depends_on in correct startup order
    - Environment variable injection via .env
```

---

### Step 4 — Required Output Files

At minimum, Agent Mode must produce:

```
project-root/
├── .env.example
├── docker-compose.yml
├── frontend/
│   ├── Dockerfile
│   └── (framework scaffold)
├── backend/
│   ├── Dockerfile
│   └── (service code)
├── gateway/
│   ├── Dockerfile              ← if gateway required
│   └── nginx.conf              ← if single-port architecture
└── infra/
    └── (supporting config, volume mounts, init scripts)
```

---

### Docker Rules for Agent Mode 🐳

Agent Mode must follow these rules throughout the build. These are non-negotiable and derived from the frozen architecture:

| Rule | Detail |
|---|---|
| Service names must match | All service names in code and config must match `docker-compose.yml` and the freeze doc |
| One Dockerfile per service | Each containerized service has its own `Dockerfile` in its own folder |
| Do not expose unnecessary ports | Only expose ports listed in the frozen port table |
| Volumes for all persistent services | Database, vector store, and cache must have named volumes |
| Gateway handles all external traffic | No service should be directly exposed externally if a gateway is in use |
| Startup order via depends_on | `docker-compose.yml` must reflect the startup dependency order from the freeze doc |
| Do not change Docker structure | Any deviation from the frozen container design must be flagged and reviewed — not silently changed |

---

### Guardrails for Agent Mode

- **Do not change the architecture unless explicitly stated** — if Agent Mode proposes a structural change, stop and review it against the freeze document before accepting
- **Explain after each step** — Agent Mode must describe what was created and why before moving to the next phase
- **One phase at a time** — do not let Agent Mode skip phases or jump ahead to code before folder structure is confirmed
- **Flag any conflict** — if a requirement in the prompt conflicts with the frozen architecture, Agent Mode must surface it immediately rather than resolve it silently

---

### Output

A working project scaffold that includes:
- Complete folder structure per frozen architecture
- Base config and environment files
- Backend service code and routes
- Frontend scaffold
- Database schema and migrations
- AI agent modules with RAG and tool integration
- Logging and error handling
- All Dockerfiles and gateway config
- Complete `docker-compose.yml`

---

### Checklist

- [ ] Agent Mode activated (not Ask or Plan Mode)
- [ ] All three input documents attached
- [ ] Tech stack fields filled in the prompt before submitting
- [ ] Folder structure created first before any code (Phase 1)
- [ ] `docker-compose.yml` skeleton created early with correct service names
- [ ] Backend routes align with frozen API contracts
- [ ] AI agent modules match the agent skill matrix
- [ ] `backend/Dockerfile` created 🐳
- [ ] `frontend/Dockerfile` created 🐳
- [ ] `gateway/Dockerfile` created (if gateway required) 🐳
- [ ] `gateway/nginx.conf` created (if single-port architecture) 🐳
- [ ] `infra/` folder created with supporting config 🐳
- [ ] `docker-compose.yml` complete — service names, ports, volumes, depends_on 🐳
- [ ] Service names consistent across all files and the freeze document 🐳
- [ ] No architectural deviations made silently — all flagged and reviewed
- [ ] Agent Mode explained what was created after each phase
