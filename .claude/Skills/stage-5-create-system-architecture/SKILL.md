---
name: stage5-system-architecture
description: Designs the complete system architecture using all prior stage outputs as aligned inputs. Use this skill when the user wants to produce a full system architecture document, define folder structure, plan frontend and backend services, design an API gateway, plan database schema, set up RAG infrastructure, allocate ports, define authentication, plan containerization, design Docker Compose structure, or produce docs/03_system_architecture.md. Trigger when the user mentions "system architecture", "folder structure", "backend services", "API gateway", "database schema", "ports allocation", "containerization strategy", "Docker Compose structure", "Dockerfile ownership", "gateway design", or wants to turn agent design and requirements into a complete architectural blueprint. Always run in Plan Mode with all four input files attached.
---

## Stage 5 — Plan Mode: System Architecture

### Purpose
Design the complete system architecture by aligning all prior stage outputs — the system architecture vision, requirement analysis, agent design, and agent skill matrix — into one authoritative architecture document.

> ⚠️ Architecture must be grounded in all four inputs. Do not design from `03_system_architecture.txt` alone — agent roles, skill boundaries, and real requirements must all be reflected in the final architecture.

---

### Why All Four Inputs Are Required

| Input File | What It Contributes |
|---|---|
| `03_system_architecture.txt` | High-level architecture vision and intended tech stack |
| `docs/01_requirement_analysis.md` | Functional modules, non-functional requirements, deployment constraints |
| `docs/02_agent_design.md` | Agent roles, workflows, RAG pipeline, memory, inter-agent APIs |
| `docs/02b_agent_skill_matrix.md` | Skill-level service boundaries, container ownership, tool/API mappings |

---

### Prerequisites

- [ ] `docs/03_system_architecture.txt` exists (Stage 2 complete)
- [ ] `docs/01_requirement_analysis.md` exists (Stage 3 complete)
- [ ] `docs/02_agent_design.md` exists (Stage 4 complete)
- [ ] `docs/02b_agent_skill_matrix.md` exists (Stage 4B complete)
- [ ] `.copilot-instructions.md` is in place at project root

---

### Step 1 — Open Copilot Chat in Plan Mode and Attach All Four Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Plan Mode** before submitting the prompt
3. Attach or reference all four files:
   ```
   docs/03_system_architecture.txt
   docs/01_requirement_analysis.md
   docs/02_agent_design.md
   docs/02b_agent_skill_matrix.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Plan Mode):

```
Based on the system architecture document, requirement analysis, agent design,
and agent skill mapping, design the complete system architecture.

Please include:

1. Folder structure
2. Frontend architecture
3. Backend services
4. API gateway
5. Database schema
6. RAG infrastructure
7. AI agent integration
8. Ports allocation
9. Authentication and authorization
10. Logging, monitoring, and error handling
11. Containerization strategy
12. Dockerfile ownership by service
13. Gateway / reverse proxy design
14. Internal vs external ports
15. Docker Compose service structure
16. Volumes / persistent storage

Create:
docs/03_system_architecture.md
```

---

### Step 3 — Expected Output Structure

Copilot should produce `docs/03_system_architecture.md` with the following sections:

```markdown
# System Architecture

## 1. Folder Structure
- Full project folder tree
- Which service owns which folder
- Naming conventions applied

## 2. Frontend Architecture
- Framework and key libraries
- Page / component structure
- State management approach
- How frontend communicates with backend / gateway

## 3. Backend Services
- Service name, responsibility, and tech stack
- Internal APIs exposed by each service
- Inter-service communication method

## 4. API Gateway
- Gateway technology (e.g. Nginx, Kong, Traefik)
- Routing rules (path → service mapping)
- Rate limiting and request validation at gateway level
- Single entry point for all external traffic

## 5. Database Schema
- Entities and relationships
- Database technology per service (if different)
- Indexing strategy
- Migration approach

## 6. RAG Infrastructure
- Vector store selection and justification
- Embedding model and pipeline
- Document ingestion flow
- Retrieval and re-ranking strategy
- Context window management

## 7. AI Agent Integration
- How agents attach to backend services
- Agent-to-service API contracts
- Shared context or memory storage location
- Tool registration and invocation flow

## 8. Ports Allocation
| Service | Internal Port | External Port | Notes |
|---|---|---|---|
| frontend | | | |
| backend | | | |
| gateway | | | |
| ai-service | | | |
| database | | | |

## 9. Authentication and Authorization
- Auth method (JWT, OAuth2, API keys, session)
- Token issuance and validation flow
- Role-based access control (RBAC) rules
- Service-to-service auth (if applicable)

## 10. Logging, Monitoring, and Error Handling
- Logging strategy and log format
- Monitoring tools and metrics collected
- Alerting thresholds
- Error handling patterns per service layer
- Distributed tracing approach (if applicable)

## 11. Containerization Strategy 🐳
- Which services are containerized
- Base image decisions per service
- Build strategy (multi-stage builds, etc.)
- Container resource constraints

## 12. Dockerfile Ownership by Service 🐳
| Service | Dockerfile Path | Base Image | Notes |
|---|---|---|---|
| frontend | frontend/Dockerfile | | |
| backend | backend/Dockerfile | | |
| gateway | gateway/Dockerfile | | |
| ai-service | ai/Dockerfile | | |

## 13. Gateway / Reverse Proxy Design 🐳
- Gateway type and justification
- Single-port vs multi-port decision
- Traffic routing rules
- SSL termination point
- How gateway container connects to backend containers

## 14. Internal vs External Ports 🐳
- External ports (exposed to host / internet)
- Internal ports (container-to-container only, not exposed)
- Port conflict resolution

## 15. Docker Compose Service Structure 🐳
- Full `docker-compose.yml` outline
- Service names, images, build paths
- Network definitions
- Depends-on and startup order
- Environment variable injection method

## 16. Volumes / Persistent Storage 🐳
- Named volumes per service
- What data is persisted vs ephemeral
- Backup strategy for persistent volumes
- Bind mounts (if used for local dev)
```

---

### Docker Architecture Checklist 🐳

Before marking `03_system_architecture.md` complete, confirm all Docker sections are addressed:

| Section | Item | Included? |
|---|---|---|
| 11 | All services classified as containerized or not | ✅ |
| 12 | Every service has a named `Dockerfile` path | ✅ |
| 13 | Gateway type decided, single vs multi-port confirmed | ✅ |
| 14 | Internal vs external ports clearly separated | ✅ |
| 15 | `docker-compose.yml` structure fully outlined | ✅ |
| 16 | Named volumes defined for all persistent data | ✅ |

---

### Output

```
docs/
└── 03_system_architecture.md    ← Complete architecture across 16 dimensions
```

This document is the authoritative reference for all implementation in Stage 6 and beyond. No service, API, or container should be built without alignment to this document.

---

### Checklist

- [ ] Plan Mode activated in Copilot Chat before submitting prompt
- [ ] All four input files attached to Copilot Chat
- [ ] Full prompt used — all 16 sections requested
- [ ] `docs/03_system_architecture.md` generated by Copilot
- [ ] All 16 sections present in the output
- [ ] Folder structure matches agent skill matrix service boundaries (Section 1)
- [ ] Port allocation table complete with no conflicts (Section 8)
- [ ] Auth method decided and flow documented (Section 9)
- [ ] All Docker sections (11–16) fully completed 🐳
- [ ] Gateway type and single/multi-port decision recorded (Section 13)
- [ ] `docker-compose.yml` structure outlined (Section 15)
- [ ] Persistent volumes identified (Section 16)
- [ ] Document reviewed and agreed before any implementation begins
