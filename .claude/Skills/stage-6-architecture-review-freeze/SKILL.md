---
name: stage6-architecture-review-freeze
description: Reviews and freezes the full system architecture before any code generation begins. Use this skill when the user wants to review all architecture documents for consistency, check for missing dependencies or conflicts, validate Docker and container decisions, confirm service-to-container alignment, or produce the final frozen architecture document docs/04_architecture_freeze.md. Trigger when the user mentions "architecture review", "architecture freeze", "frozen design", "review architecture", "check consistency", "implementation ready", "pre-build review", "container boundaries review", or wants a final sign-off document before Agent Mode starts building code. This stage is mandatory — do not begin code generation without it.
---

## Stage 6 — Architecture Review and Freeze

### Purpose
Before any code is generated, use Ask or Plan Mode to instruct Copilot to cross-review all architecture documents for consistency, conflicts, and missing dependencies — then produce a single frozen architecture document that Agent Mode can reliably reference throughout the entire build.

> ⚠️ This is a mandatory gate. Code generation in Agent Mode must not begin until `docs/04_architecture_freeze.md` exists and has been reviewed by the team.

---

### Why This Stage Is Essential

By Stage 6, you have produced:
- Requirement analysis
- Agent design
- Agent skill matrix
- Workflow design
- System architecture

Each was generated from different inputs at different times. Inconsistencies accumulate silently across documents. This stage surfaces them before they become bugs.

Without a freeze document, Agent Mode has no single reliable reference — it may generate code that conflicts with earlier design decisions or misses dependencies entirely.

---

### Prerequisites

- [ ] `docs/01_requirement_analysis.md` exists (Stage 3)
- [ ] `docs/02_agent_design.md` exists (Stage 4)
- [ ] `docs/02b_agent_skill_matrix.md` exists (Stage 4B)
- [ ] `docs/02c_workflow_design.md` exists (Stage 5B)
- [ ] `docs/03_system_architecture.md` exists (Stage 5)
- [ ] `.copilot-instructions.md` is in place at project root

---

### Step 1 — Open Copilot in Ask or Plan Mode and Attach All Documents

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Use **Ask Mode** for review and conflict detection, or **Plan Mode** if you want Copilot to also propose fixes
3. Attach or reference all documents:
   ```
   docs/01_requirement_analysis.md
   docs/02_agent_design.md
   docs/02b_agent_skill_matrix.md
   docs/02c_workflow_design.md
   docs/03_system_architecture.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat:

```
Please review the requirement analysis, agent design, agent skill mapping,
workflow design, and system architecture.

Check for:
- Inconsistency between documents
- Missing dependencies
- Architecture conflicts
- Skill-to-agent mismatches
- Implementation risks
- Docker and container boundaries consistency
- Service-to-container alignment
- Gateway necessity confirmed or denied
- Internal vs external port exposure correctness
- Persistent volume requirements
- Deployment consistency across services
- Frontend / backend / gateway dockerization confirmed
- Startup dependency order

If aligned, provide a final implementation-ready summary and freeze the architecture.

Create:
docs/04_architecture_freeze.md
```

---

### Step 3 — Expected Output Structure

Copilot should produce `docs/04_architecture_freeze.md` with the following sections:

```markdown
# Architecture Freeze Document

> Status: FROZEN — Do not modify without a formal change review.
> Frozen on: [date]

---

## 1. Review Summary

### Inconsistencies Found
| Document A | Document B | Inconsistency | Resolution |
|---|---|---|---|
| (doc name) | (doc name) | (what conflicts) | (how resolved) |

### Missing Dependencies Identified
| Item | Missing From | Impact | Resolution |
|---|---|---|---|

### Architecture Conflicts
| Conflict | Affected Services | Resolution |
|---|---|---|

### Skill-to-Agent Mismatches
| Skill | Assigned Agent | Correct Agent | Resolution |
|---|---|---|---|

### Implementation Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|

---

## 2. Frozen Architecture Decisions

### Services and Responsibilities
| Service | Responsibility | Tech Stack | Owner Agent / Module |
|---|---|---|---|

### API Contracts (Frozen)
| Endpoint | Method | Owner Service | Consumer | Auth Required |
|---|---|---|---|---|

### Data Flow (Frozen)
- (Step-by-step description of data moving through the system)

### Agent-to-Service Mapping (Frozen)
| Agent | Owned Service | Callable Services |
|---|---|---|

---

## 3. Docker and Container Freeze 🐳

### Container Boundaries
| Container Name | Service(s) Inside | Dockerfile Path | Justification |
|---|---|---|---|

### Gateway Decision
- Gateway required: Yes / No
- Gateway technology: (e.g. Nginx, Traefik, Kong)
- Reason: (why this gateway, or why no gateway)
- Routes handled: (list of path → service mappings)

### Port Exposure (Frozen)
| Service | Internal Port | External Port | Exposed to Host? | Notes |
|---|---|---|---|---|

### Persistent Volume Requirements
| Service | Volume Name | Mount Path | Data Type | Backup Required? |
|---|---|---|---|---|

### Startup Dependency Order
```
1. database
2. cache (if applicable)
3. ai-service
4. backend
5. gateway
6. frontend
```
(Adjust to match actual services — this order must be reflected in docker-compose `depends_on`)

### Dockerization Confirmation
| Service | Containerized | Dockerfile Confirmed | docker-compose Entry |
|---|---|---|---|
| frontend | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ |
| backend | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ |
| gateway | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ |
| ai-service | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ |
| database | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ |

---

## 4. Implementation-Ready Summary

### What to Build First
- (Ordered list of services / modules to implement, based on dependency order)

### Key Constraints for Agent Mode
- (Rules Agent Mode must follow when generating code)
- (Folder structure constraints)
- (Naming conventions)
- (Docker rules — do not deviate from frozen container structure)

### Acceptance Criteria Reminder
- (Restate from requirement analysis — what "done" looks like)

---

## 5. Freeze Sign-Off

| Reviewer | Role | Status | Notes |
|---|---|---|---|
| | | Approved / Pending | |

> Once all reviewers have approved, set status to FROZEN.
> Any changes after this point require a formal architecture change request.
```

---

### Docker Review Checklist 🐳

Before marking the freeze document complete, confirm all Docker items pass:

| Item | Check |
|---|---|
| Container boundaries are consistent across all documents | ✅ |
| Gateway is required or explicitly not required — with reason | ✅ |
| Frontend, backend, and gateway dockerization all confirmed | ✅ |
| Internal vs external port exposure is correct and conflict-free | ✅ |
| All persistent services (DB, vector store, cache) have named volumes | ✅ |
| Startup dependency order is sensible and reflected in `depends_on` | ✅ |

---

### Output

```
docs/
└── 04_architecture_freeze.md    ← Frozen reference for all Agent Mode code generation
```

This is the single source of truth for Agent Mode. Every file, service, API, and container generated in Stage 7 and beyond must align with this document.

---

### Checklist

- [ ] Ask or Plan Mode activated before submitting prompt
- [ ] All five documents attached to Copilot Chat
- [ ] Full prompt used — all review items included
- [ ] `docs/04_architecture_freeze.md` generated by Copilot
- [ ] All 5 sections present: review summary, frozen decisions, Docker freeze, implementation summary, sign-off
- [ ] All inconsistencies found are listed and resolved (Section 1)
- [ ] Frozen API contracts defined (Section 2)
- [ ] Docker container freeze table complete (Section 3) 🐳
- [ ] Gateway decision recorded with justification (Section 3) 🐳
- [ ] Port exposure table complete — no conflicts (Section 3) 🐳
- [ ] Persistent volumes defined for all stateful services (Section 3) 🐳
- [ ] Startup dependency order confirmed (Section 3) 🐳
- [ ] Dockerization confirmation table fully filled (Section 3) 🐳
- [ ] Implementation-ready summary includes rules for Agent Mode (Section 4)
- [ ] Sign-off table completed before Agent Mode begins (Section 5)
