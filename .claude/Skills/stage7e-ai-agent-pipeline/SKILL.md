---
name: stage7e-ai-agent-pipeline
description: Implements the full 7-agent AI pipeline using CrewAI framework. Use this skill when the user wants to build AI agents, implement CrewAI orchestration, create a routing agent, data extraction agent, RAG verification agent, summarization agent, validation agent, memory agent, or security agent. Trigger when the user mentions "AI agents", "CrewAI", "agent pipeline", "7 agents", "routing agent", "extraction agent", "summarization", "RAG verification", "memory agent", "security agent", "prompt injection", "agent orchestration", or wants to implement Stage 7E after document upload is working.
---

## Stage 7E — Agent Mode: AI Agent Pipeline Module

### Purpose
Implement the complete 7-agent AI pipeline using CrewAI as the orchestration framework. Each agent has a specific role in processing uploaded documents — from routing and extraction through to summarization, validation, memory management, and security.

> ⚠️ Do NOT change the architecture, docker-compose.yml, or port assignments. Implementation only.

---

### Prerequisites

- [ ] Stage 7D complete — document upload + transcription working
- [ ] `docs/02_agent_design.md` exists (agent roles and workflows)
- [ ] `docs/02b_agent_skill_matrix.md` exists (skills per agent)
- [ ] `rag_service/app/main.py` exists (RAG service scaffold)
- [ ] Qdrant vector store running
- [ ] OpenRouter / DeepSeek API key available
- [ ] Redis running (for memory agent)

---

### Step 1 — Switch to Agent Mode and Attach Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach all three input files:
   ```
   docs/02_agent_design.md
   docs/02b_agent_skill_matrix.md
   rag_service/app/main.py
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Agent Mode):

```
Implement the 7 AI Agents using CrewAI framework in rag_service.

Agent 1 — Routing Agent:
- Classify incoming document/request
- Determine which agents to invoke
- Route to correct pipeline path

Agent 2 — Data Extraction Agent:
- Parse transcripts and documents
- Extract: action items, decisions, dates, owners, requirements
- Output structured JSON

Agent 3 — RAG Verification Agent:
- Query Qdrant vector store
- Retrieve relevant context with citations
- Filter by project_id scope
- Output: context + [doc_id#section] citations

Agent 4 — Summarization Agent:
- Generate meeting minutes from transcript
- Draft BRD (Business Requirements Document)
- Output structured documents

Agent 5 — Validation Agent:
- Detect high-risk content
- Check completeness of extracted data
- Trigger HITL if confidence < threshold
- Output: validation_result + risk_flags

Agent 6 — Memory Agent:
- Store short-term context in Redis
- Store long-term context in PostgreSQL
- Retrieve relevant past context for current session

Agent 7 — Security Agent:
- Detect prompt injection attempts
- Validate input safety
- Log security events

Create:
- rag_service/app/agents/ (one file per agent)
- rag_service/app/skills/ (skills per agent)
- rag_service/app/services/crewai_orchestrator.py

Constraints:
- Do NOT change architecture or docker-compose.yml
- Use CrewAI framework
- All agents must log their state to agent_state table
```

---

### Step 3 — Expected Output Files

```
rag_service/app/
├── agents/
│   ├── routing_agent.py
│   ├── extraction_agent.py
│   ├── rag_verification_agent.py
│   ├── summarization_agent.py
│   ├── validation_agent.py
│   ├── memory_agent.py
│   └── security_agent.py
├── skills/
│   ├── extraction_skills.py
│   ├── rag_skills.py
│   ├── summarization_skills.py
│   └── validation_skills.py
└── services/
    └── crewai_orchestrator.py
```

---

### Step 4 — Agent Responsibilities Reference

| Agent | Input | Output | Triggers HITL? |
|---|---|---|---|
| Routing | Raw document/request | Pipeline route decision | No |
| Data Extraction | Transcript text | Structured JSON (actions, decisions) | No |
| RAG Verification | Query + project_id | Context + citations | No |
| Summarization | Extracted data + RAG context | Meeting minutes + BRD draft | No |
| Validation | All agent outputs | Risk flags + confidence score | Yes (low confidence) |
| Memory | Session context | Stored/retrieved context | No |
| Security | Any input | Safe/unsafe classification | Yes (injection detected) |

---

### Step 5 — Acceptance Tests (Must All Pass)

#### Test 1 — Execute Workflow
```powershell
$token = "your_access_token"
$body = '{"document_id":"test-doc-id","project_id":"660e8400-..."}'
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5002/rag/workflow/execute" `
  -Headers @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" } `
  -Body $body
# Expected: { agent_state: [6+ records], status: "COMPLETED" }
```

#### Test 2 — Meeting Minutes Generated
- Check PostgreSQL `documents` table → meeting_minutes field populated ✅

#### Test 3 — RAG Has Results
```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5002/rag/search" `
  -Headers @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" } `
  -Body '{"query":"requirements","project_id":"660e8400-..."}'
# Expected: results with citations
```

#### Test 4 — Agent State Logged
- Check PostgreSQL `agent_state` table → 6+ records per workflow run ✅

---

### Output

```
rag_service/app/agents/          ← 7 agent implementation files
rag_service/app/skills/          ← Skill modules per agent
rag_service/app/services/
  crewai_orchestrator.py         ← CrewAI crew setup and execution
```

---

### Checklist

- [ ] Agent Mode activated before submitting prompt
- [ ] All three input files attached
- [ ] All 7 agents implemented as individual files
- [ ] CrewAI framework used for orchestration
- [ ] Routing agent classifies correctly
- [ ] Extraction agent outputs structured JSON
- [ ] RAG verification agent queries Qdrant with project_id filter
- [ ] Summarization agent generates meeting minutes + BRD draft
- [ ] Validation agent detects risk and triggers HITL when needed
- [ ] Memory agent uses Redis (short-term) + PostgreSQL (long-term)
- [ ] Security agent detects prompt injection
- [ ] Agent state logged to `agent_state` table per step
- [ ] All 4 acceptance tests pass
- [ ] 🔒 All tests pass before proceeding to Stage 7F
