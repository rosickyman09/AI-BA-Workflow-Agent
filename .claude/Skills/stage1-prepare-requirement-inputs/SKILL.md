---
name: stage1-prepare-requirement-inputs
description: Prepares all requirement inputs before any code generation begins. Use this skill when starting to gather project requirements, filling in a requirement document, preparing user stories, defining system scope, or producing a structured input document for AI to break down further. Trigger when the user mentions "requirement document", "prepare requirements", "fill in requirements", "project spec", "solution template", or wants to document what they need before building anything.
---

<!-- Tip: Use /create-skill in chat to generate content with agent assistance -->

Stage 1 — Prepare Requirement Inputs
Purpose
Produce one complete, structured requirement source so that AI (Copilot) can break it down into tasks, architecture, and implementation steps accurately.

Step 1 — Ready the User Requirement Document
Before filling in the template, gather answers to the following:
AreaQuestions to AnswerProject GoalWhat problem does this solve? Who are the users?ScopeWhat is IN scope? What is explicitly OUT of scope?FeaturesWhat are the must-have features? Nice-to-have?Tech PreferencesAny preferred languages, frameworks, or platforms?IntegrationsExternal APIs, databases, third-party services?Non-FunctionalPerformance, security, scalability requirements?TimelineAny deadlines or phased delivery expectations?ConstraintsBudget, team size, existing systems to work with?

Step 2 — Fill in the VS Code Copilot Solution Requirement Template
Create a file at:
requirements/requirement-document.md
Use the template below and fill in every section before asking Copilot to generate anything:
markdown# VS Code Copilot — Complete Solution Requirement Document

## 1. Project Overview
- **Project Name:**
- **Project Goal:** (What problem are we solving?)
- **Target Users:** (Who will use this system?)
- **Project Type:** (Web app / API / CLI tool / Desktop app / Other)

## 2. Scope

### In Scope
- (List features and functions that MUST be built)

### Out of Scope
- (List things explicitly NOT being built in this phase)

## 3. Functional Requirements

### Must-Have Features (P1)
- [ ] Feature 1 — (brief description)
- [ ] Feature 2 — (brief description)

### Nice-to-Have Features (P2)
- [ ] Feature A — (brief description)

### Future Considerations (P3)
- [ ] Feature X — (not in this phase)

## 4. Technical Requirements

- **Frontend:** (e.g. React, Vue, plain HTML — or N/A)
- **Backend:** (e.g. Node.js, Python FastAPI, .NET — or N/A)
- **Database:** (e.g. PostgreSQL, MongoDB, SQLite — or N/A)
- **Gateway / Proxy:** (e.g. Nginx, Kong, Traefik — or N/A)
- **Infrastructure:** (e.g. Docker, Kubernetes, cloud provider — or N/A)
- **Authentication:** (e.g. JWT, OAuth2, session-based — or N/A)

## 5. System Architecture Overview
<!-- Describe or sketch the intended architecture -->
<!-- e.g. Single-port via gateway → backend → database -->

## 6. External Integrations
- (List any third-party APIs, services, or systems to integrate with)

## 7. Non-Functional Requirements

- **Performance:** (e.g. response time < 200ms, support 1000 concurrent users)
- **Security:** (e.g. HTTPS only, input validation, rate limiting)
- **Scalability:** (e.g. horizontal scaling required)
- **Availability:** (e.g. 99.9% uptime)

## 8. Constraints & Assumptions
- (List known constraints: budget, team size, deadlines, legacy systems)
- (List assumptions being made)

## 9. Acceptance Criteria
- (How will we know when this is done? What does "done" look like?)

## 10. Open Questions
- (List anything still unresolved that needs a decision)

Output
A single, complete requirements/requirement-document.md file that:

Covers all functional and non-functional needs
Is specific enough for Copilot to break into architecture and tasks
Serves as the single source of truth for the entire project


Checklist

 All stakeholder inputs gathered before filling in the template
 requirements/ folder exists at project root
 requirement-document.md created and all sections filled
 Scope clearly defines what is IN and OUT
 Tech stack decisions recorded (even if tentative)
 Open questions listed so nothing is silently assumed
 Document reviewed before handing to Copilot for breakdown