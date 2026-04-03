---
name: stage4b-agent-capability-mapping
description: Converts agent design into a detailed skill matrix before system architecture begins. Use this skill when the user wants to map agent capabilities, define skills owned and callable per agent, specify tools per skill, plan service boundaries from agent roles, or produce docs/02b_agent_skill_matrix.md. Trigger when the user mentions "agent capability mapping", "skill matrix", "agent skills", "skills owned by agent", "callable skills", "handoff between agents", "service boundaries from agents", or wants to bridge agent design and system architecture using a capability map. Always run this after Stage 4 and before Stage 5 — do not skip.
---

## Stage 4B — Plan Mode: Agent Capability Mapping

### Purpose
Bridge the gap between agent design (Stage 4) and system architecture (Stage 5) by mapping each agent's skills in detail. System architecture — including service boundaries, module design, API design, data flow, RAG/tool integration, and Docker structure — should be built from this capability map, not directly from the high-level agent design alone.

> ⚠️ Do not skip this stage. Architecture built without a skill matrix produces misaligned service boundaries and poorly scoped APIs.

---

### Why This Stage Exists

`docs/02_agent_design.md` defines agent roles and workflows at a high level.  
`docs/02b_agent_skill_matrix.md` goes one level deeper — it answers:

- What specific skills does each agent own?
- Which skills can each agent call from other agents?
- What tools does each skill use?
- What are the exact inputs, outputs, validation rules, and fallback paths?
- Which skills map to backend containers, AI service containers, or external managed services?

This granularity is what makes system architecture decisions defensible — especially for service boundaries, module design, API contracts, data flow, and Docker container planning.

---

### Prerequisites

- [ ] `docs/01_requirement_analysis.md` exists (Stage 3 complete)
- [ ] `docs/02_agent_design.md` exists (Stage 4 complete)
- [ ] `.copilot-instructions.md` is in place at project root

---

### Step 1 — Open Copilot Chat in Plan Mode and Attach Both Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Plan Mode** before submitting the prompt
3. Attach or reference **both** files:
   ```
   docs/01_requirement_analysis.md
   docs/02_agent_design.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Plan Mode):

```
Based on the requirement analysis and agent design, create an agent capability mapping document.

For each AI agent, define:

1. Agent name
2. Agent responsibility
3. Skills owned by this agent
4. Skills callable by this agent
5. Tools used by each skill
6. Input / output of each skill
7. Validation / fallback
8. Handoff to next agent
9. Backend container
10. Separate AI service container
11. External managed service

Create:
docs/02b_agent_skill_matrix.md
```

---

### Step 3 — Expected Output Structure

Copilot should produce `docs/02b_agent_skill_matrix.md` with the following structure, **repeated for each agent**:

```markdown
# Agent Capability Matrix

---

## Agent: [Agent Name]

### 1. Agent Responsibility
- (What this agent is accountable for end-to-end)

### 2. Skills Owned by This Agent
| Skill Name | Description |
|---|---|
| skill_name | what it does |

### 3. Skills Callable by This Agent
| Skill Name | Owned By Agent | Purpose |
|---|---|---|
| skill_name | OtherAgent | why this agent calls it |

### 4. Tools Used by Each Skill
| Skill Name | Tool | Purpose |
|---|---|---|
| skill_name | tool_name | what the tool does for this skill |

### 5. Input / Output of Each Skill
| Skill Name | Input | Output |
|---|---|---|
| skill_name | input schema / description | output schema / description |

### 6. Validation / Fallback
| Skill Name | Validation Rule | Fallback Behaviour |
|---|---|---|
| skill_name | what is validated | what happens on failure |

### 7. Handoff to Next Agent
| Condition | Next Agent | Data Passed |
|---|---|---|
| trigger condition | AgentName | what data is handed off |

### 8. Backend Container
- Container name:
- Responsibilities handled here:
- Port:

### 9. Separate AI Service Container
- Container name: (or N/A)
- Model / service hosted:
- Port:

### 10. External Managed Service
- Service name: (or N/A)
- Provider:
- Integration method (API, SDK, webhook):

---
```

---

### How This Feeds System Architecture 🏗️

Once `02b_agent_skill_matrix.md` is complete, use it to drive the following decisions in Stage 5:

| Architecture Decision | Driven By |
|---|---|
| Service boundaries | Skills owned per agent → one service per agent or skill cluster |
| Module design | Skills owned → internal modules within a service |
| API design | Skills callable → defines inter-service API contracts |
| Data flow | Input/output per skill → defines data passing between services |
| RAG / tool integration | Tools per skill → defines where vector stores and tool APIs attach |
| Docker container plan 🐳 | Sections 8–10 → maps each agent to backend container, AI container, or external service |

---

### Docker Planning from Sections 8–10 🐳

Use the three container classification fields to produce the Docker structure:

| Field | Maps To |
|---|---|
| Backend container | A service in `docker-compose.yml` with its own `Dockerfile` |
| Separate AI service container | A dedicated AI/ML container (e.g. LLM server, embedding service) |
| External managed service | No container needed — configure via env vars / API keys |

This prevents over-containerizing external services and ensures AI workloads are isolated from business logic containers.

---

### Output

```
docs/
└── 02b_agent_skill_matrix.md    ← Full capability map for all agents
```

This document is the direct input to Stage 5 system architecture. Do not begin architecture or service design without it.

---

### Checklist

- [ ] Plan Mode activated in Copilot Chat before submitting prompt
- [ ] Both input files attached (`01_requirement_analysis.md` + `02_agent_design.md`)
- [ ] Full prompt used — all 11 fields requested
- [ ] `docs/02b_agent_skill_matrix.md` generated by Copilot
- [ ] Every agent has all 11 sections completed
- [ ] Skills owned vs skills callable clearly distinguished per agent (Sections 3 & 4)
- [ ] Every skill has input/output schema defined (Section 6)
- [ ] Validation rules and fallback behaviour defined for every skill (Section 7)
- [ ] Handoff conditions and data passed are explicit (Section 8)
- [ ] Each agent classified into backend container / AI container / external service (Sections 9–11) 🐳
- [ ] Document reviewed before moving to Stage 5
