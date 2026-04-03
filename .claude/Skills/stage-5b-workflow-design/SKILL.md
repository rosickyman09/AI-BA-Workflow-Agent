---
name: stage5b-workflow-design
description: Designs the system workflow and sub-workflows to bridge agent design and system architecture. Use this skill when the user wants to map end-to-end workflows, define sub-workflows, specify event triggers, plan workflow orchestration, design failure handling and retry strategies, or identify human-in-the-loop checkpoints. Trigger when the user mentions "workflow design", "system workflow", "sub-workflows", "event triggers", "workflow orchestration", "retry strategy", "failure handling", "human-in-the-loop", or wants to produce docs/02c_workflow_design.md. Always run this after Stage 4B (skill matrix) and before Stage 5 (system architecture) — skipping this stage causes ambiguous architecture boundaries.
---

## Stage 5B — Workflow Design

### Purpose
Define the system's main workflow and all sub-workflows before finalising system architecture. Without this step, architecture diagrams can be drawn without a clear picture of how data and control actually flow through the system — leading to missing APIs, undefined failure paths, and unclear service boundaries.

> ⚠️ This stage sits between agent skill mapping (Stage 4B) and system architecture (Stage 5). Do not skip it. Architecture decisions should reflect workflow reality, not just component diagrams.

---

### Why This Stage Exists

The current design chain is:

```
Agent Design (Stage 4)
  → Skill Mapping (Stage 4B)
  → [Workflow Design — this stage]
  → System Architecture (Stage 5)
```

Without workflow design, the architecture may show services and containers clearly, but leave unanswered:
- In what order do things happen?
- What triggers each step?
- What happens when something fails mid-workflow?
- Where does a human need to intervene?
- How are retries and timeouts handled?

`docs/02c_workflow_design.md` answers all of these — making Stage 5 architecture decisions precise and defensible.

---

### Prerequisites

- [ ] `docs/01_requirement_analysis.md` exists (Stage 3 complete)
- [ ] `docs/02_agent_design.md` exists (Stage 4 complete)
- [ ] `docs/02b_agent_skill_matrix.md` exists (Stage 4B complete)
- [ ] `.copilot-instructions.md` is in place at project root

---

### Step 1 — Open Copilot Chat and Attach Both Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Attach or reference both files:
   ```
   docs/01_requirement_analysis.md
   docs/02_agent_design.md
   ```
3. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat:

```
Based on the requirement analysis and agent design, design the system workflow
and sub-workflows.

Please include:

1. Main workflow
2. Sub-workflows
3. Event triggers
4. Workflow orchestration
5. Failure handling
6. Retry strategy
7. Human-in-the-loop points

Create:
docs/02c_workflow_design.md
```

---

### Step 3 — Expected Output Structure

Copilot should produce `docs/02c_workflow_design.md` with the following sections:

```markdown
# Workflow Design

## 1. Main Workflow
- End-to-end flow from user entry point to final output
- Step-by-step sequence (numbered)
- Which agent or service owns each step
- Data passed between steps
- Text-based sequence diagram

## 2. Sub-Workflows
For each sub-workflow, define:
- Sub-workflow name and purpose
- Trigger condition (what starts it)
- Steps in sequence
- Owner (agent / service / human)
- Output and where it goes next

### Example sub-workflows to consider:
- Document ingestion workflow
- RAG retrieval workflow
- Agent handoff workflow
- Validation workflow
- Notification / reporting workflow

## 3. Event Triggers
| Event Name | Source | Target | Payload | Condition |
|---|---|---|---|---|
| (event) | (who fires it) | (who receives it) | (data sent) | (when it fires) |

Types of triggers to cover:
- User-initiated triggers (button click, API call, form submit)
- System-initiated triggers (scheduled jobs, file upload complete, threshold exceeded)
- Agent-initiated triggers (agent completes task, agent requests handoff)
- Error triggers (timeout, validation failure, low-confidence output)

## 4. Workflow Orchestration
- Orchestration method (e.g. event bus, message queue, direct call, workflow engine)
- Synchronous vs asynchronous steps — which are which and why
- How parallel branches are managed
- How workflow state is tracked
- Tooling used (e.g. Celery, Temporal, Prefect, LangGraph, custom)

## 5. Failure Handling
| Workflow / Step | Failure Type | Handling Strategy | Escalation Path |
|---|---|---|---|
| (step name) | (what can fail) | (how it's handled) | (what happens if handling fails) |

Failure types to address:
- Agent returns empty or low-confidence output
- External API timeout or error
- Database write failure
- RAG retrieval returns no results
- Validation failure mid-workflow
- Partial completion before crash

## 6. Retry Strategy
| Step | Retryable? | Max Retries | Backoff Strategy | On Final Failure |
|---|---|---|---|---|
| (step name) | Yes / No | (number) | (immediate / linear / exponential) | (fallback action) |

Considerations:
- Idempotency — is it safe to retry this step?
- Backoff type per step (immediate for fast ops, exponential for external APIs)
- Dead-letter queue or error log for non-retryable failures

## 7. Human-in-the-Loop Points
| Trigger Condition | What the Human Sees | Action Required | Timeout Behaviour |
|---|---|---|---|
| (when HITL activates) | (what is presented for review) | (approve / reject / edit) | (what happens if no response) |

Scenarios to define HITL for:
- Low-confidence AI output requiring review
- High-risk action (deletion, financial transaction, external publish)
- Ambiguous input needing clarification before proceeding
- Regulatory or compliance checkpoint
- Escalation from automated failure handling
```

---

### How This Feeds System Architecture

Once `02c_workflow_design.md` is complete, use it to clarify the following in Stage 5:

| Architecture Decision | Driven By |
|---|---|
| Service responsibilities | Main workflow step ownership → which service handles what |
| API design | Step-to-step data passing → defines request/response contracts |
| Async vs sync service calls | Workflow orchestration section → sync vs async per step |
| Message queue / event bus need | Orchestration method → confirms if a queue service is needed |
| Error handling per service | Failure handling table → each service knows its failure contract |
| Container design | Sub-workflow ownership → helps group related steps into one container |
| HITL UI requirements | Human-in-the-loop points → identifies if a review UI or notification system is needed |

---

### Output

```
docs/
└── 02c_workflow_design.md    ← Complete workflow design across 7 dimensions
```

This document sits alongside the agent skill matrix as a direct input to Stage 5 system architecture. Both must be complete before architecture design begins.

---

### Checklist

- [ ] Both input files attached to Copilot Chat (`01_requirement_analysis.md` + `02_agent_design.md`)
- [ ] Full prompt used — all 7 sections requested
- [ ] `docs/02c_workflow_design.md` generated by Copilot
- [ ] All 7 sections present in the output
- [ ] Main workflow includes a text-based sequence diagram (Section 1)
- [ ] Every sub-workflow has a named trigger condition (Section 2)
- [ ] Event triggers table covers user, system, agent, and error trigger types (Section 3)
- [ ] Orchestration method decided — sync vs async steps identified (Section 4)
- [ ] Failure handling table covers all critical steps (Section 5)
- [ ] Retry table clarifies idempotency and backoff per step (Section 6)
- [ ] Human-in-the-loop points defined with timeout behaviour (Section 7)
- [ ] Document reviewed before moving to Stage 5 system architecture
