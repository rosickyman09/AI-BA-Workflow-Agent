---
name: stage2-generate-4-core-txt-documents
description: Generates the 4 core planning documents from a completed requirement template. Use this skill when the user has a filled requirement document and wants to produce project planning outputs, generate architecture documents, create a deployment plan, define AI agent architecture, or produce the core txt files that drive the rest of the build. Trigger when the user mentions "generate documents", "core documents", "project requirement txt", "system architecture doc", "deployment plan", "AI agent architecture", or wants Copilot to turn their requirements into structured planning files.
---

<!-- Tip: Use /create-skill in chat to generate content with agent assistance -->

Stage 2 — Generate 4 Core TXT Documents
Purpose
Use the completed requirement document from Stage 1 to instruct Copilot to produce four structured planning files. These become the single source of truth for architecture, deployment, and implementation in all later stages.

Prerequisites
Before running this stage, confirm:

 requirements/requirement-document.md is fully filled in (Stage 1 complete)
 .copilot-instructions.md is in place at project root (Stage 0 complete)
 docs/ folder exists at project root


Step 1 — Output File Naming Convention
All four files must follow this exact naming format and be saved to docs/:
docs/
├── 01_project_requirement.txt
├── 02_ai_agent_architecture.txt
├── 03_system_architecture.txt
└── 04_deployment_plan.txt

Use this naming consistently across all projects so Copilot can always locate and reference them by number.


Step 2 — Prompt Copilot to Generate Each Document
Open Copilot Chat and use the prompts below one at a time, in order.

📄 Document 01 — Project Requirement
Prompt to use:
Based on requirements/requirement-document.md, generate docs/01_project_requirement.txt.
This file should summarise: project goal, target users, in-scope features (P1/P2/P3),
out-of-scope items, tech stack decisions, and acceptance criteria.
Write it as a clear, concise reference document.
Expected content:

Project goal and user summary
Prioritised feature list (P1 must-have, P2 nice-to-have, P3 future)
Explicit out-of-scope items
Agreed tech stack
Acceptance criteria


🤖 Document 02 — AI Agent Architecture
Prompt to use:
Based on requirements/requirement-document.md, generate docs/02_ai_agent_architecture.txt.
Define how AI agents or Copilot will be used in this project:
what tasks they handle, what they should not do, how they interact with the codebase,
and any prompt patterns or constraints to follow.
Expected content:

Role of AI/Copilot in the project
What Copilot is responsible for generating
What Copilot must NOT touch or change
Prompt patterns the team will use
Agent boundaries and handoff points


🏗️ Document 03 — System Architecture
Prompt to use:
Based on requirements/requirement-document.md, generate docs/03_system_architecture.txt.
Include: all services and their responsibilities, containerization approach,
service boundaries, whether a gateway is needed, single-port vs multi-port design,
data flow between services, and any external integrations.
Expected content (must include Docker decisions):

All services listed with their responsibilities
Containerized vs non-containerized per service
Service boundaries clearly defined
Gateway: required or not, and why
Single-port vs multi-port decision with justification
Data flow diagram (text-based)
External integrations and how they connect


🚀 Document 04 — Deployment Plan
Prompt to use:
Based on requirements/requirement-document.md and docs/03_system_architecture.txt,
generate docs/04_deployment_plan.txt.
Include: Docker Compose as the deployment method, each service's Dockerfile location,
port mappings, environment variable strategy, health checks, and deployment steps.
Expected content (must include Docker decisions):

Docker Compose as the primary deployment method
Each service mapped to its Dockerfile location
Port mappings (host:container) for all services
Environment variable strategy (.env files, secrets handling)
Health check definitions per service
Step-by-step deployment instructions
Rollback approach


Docker Requirements for Documents 03 & 04 🐳
Both 03_system_architecture.txt and 04_deployment_plan.txt must address the following before being considered complete:
RequirementDocument 03Document 04Containerized services listed✅✅Service boundaries defined✅—Gateway needed or not✅✅Single-port vs multi-port decision✅✅Docker Compose as deployment method—✅Dockerfile location per service—✅Port mappings—✅

Output
Four complete files in docs/:
docs/
├── 01_project_requirement.txt      ← What we're building and why
├── 02_ai_agent_architecture.txt    ← How Copilot/AI is used in this project
├── 03_system_architecture.txt      ← Services, containers, gateway, data flow
└── 04_deployment_plan.txt          ← Docker Compose, ports, env vars, steps
These four files drive all subsequent stages. Do not begin coding until all four are generated and reviewed.

Checklist

 docs/01_project_requirement.txt generated and reviewed
 docs/02_ai_agent_architecture.txt generated and reviewed
 docs/03_system_architecture.txt generated — includes containerization, gateway, port decisions
 docs/04_deployment_plan.txt generated — includes Docker Compose, Dockerfiles, port mappings
 All four files use the exact naming convention above
 No coding has started yet — documents reviewed first