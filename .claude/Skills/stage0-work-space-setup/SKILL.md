---
name: stage0-workspacesetup
description: Sets up a consistent GitHub Copilot workspace for any new project. Use this skill when starting a new project, scaffolding a project root, creating .copilot-instructions.md, setting up Docker rules, or organizing folders like docs/, prompts/, requirements/, frontend/, backend/, gateway/, and infra/. Helps Copilot follow consistent rules across the entire project from day one.
---

<!-- Tip: Use /create-skill in chat to generate content with agent assistance -->

Stage 0 — Workspace Setup
Purpose
Ensure GitHub Copilot has consistent rules across the entire project from the start.

Step 1 — Scaffold the Project Root
Create the following at the project root:
Required:

.copilot-instructions.md
docs/

Optional (pre-create as placeholders based on project needs):

prompts/ — reusable Copilot prompt templates
requirements/ — feature or system requirements
frontend/ — client-side code (reserve if planned)
backend/ — server-side code (reserve if planned)
gateway/ — API gateway config (reserve if planned)
infra/ — infrastructure-as-code (reserve if planned)


Step 2 — Create .copilot-instructions.md
Place this file at the project root (not inside any subfolder).
Starter Template
markdown# Copilot Instructions

## Project Overview
<!-- Describe the project in 2–3 sentences -->

## Architecture
<!-- Describe the system architecture -->

## Coding Standards
- Language: <!-- e.g. TypeScript, Python -->
- Style guide: <!-- e.g. ESLint + Prettier, PEP8 -->
- Naming conventions: <!-- e.g. camelCase for variables -->

## Folder Structure Rules
- `frontend/` — all client-side code
- `backend/` — all server-side code
- `gateway/` — API gateway or reverse proxy config
- `infra/` — infrastructure-as-code
- `docs/` — architecture decisions and documentation
- Do not reorganize this structure without explicit approval

## Docker Rules
- All major services should be containerized
- Each major service should have its own Dockerfile
- Use docker-compose.yml to orchestrate services
- Gateway should be containerized if single-port architecture is used
- Ports and service names must align with the approved system architecture
- Do not change Docker structure unless explicitly asked

## What Copilot Should NOT Do
- Do not suggest moving files between top-level folders
- Do not change Docker structure unless explicitly asked
- Do not add new dependencies without noting them
- Do not assume a framework unless specified

Step 3 — Verify Copilot Is Reading the Instructions

Open any project file in VS Code
Open Copilot Chat (Ctrl+Shift+I / Cmd+Shift+I)
Ask: "What are the Docker rules for this project?"
Copilot should reflect the rules from your .copilot-instructions.md

If Copilot does not reflect your rules, check:

File is named exactly .copilot-instructions.md (with leading dot)
File is at the project root, not inside a subfolder
GitHub Copilot extension is installed and active in VS Code


Docker Rules Reference
RuleDetailContainerize all major servicesfrontend, backend, gateway each get their own containerOne Dockerfile per serviceeach service directory has its own Dockerfiledocker-compose.yml at rootsingle orchestration file at the project rootGateway containerizedrequired for single-port / reverse-proxy architecturePorts match architecturedo not change defined ports without architectural reviewNo unilateral Docker changesCopilot must not restructure Docker unless explicitly asked

Checklist

 .copilot-instructions.md created at project root
 docs/ folder created
 Optional placeholder folders created (frontend/, backend/, etc.)
 Docker rules added to .copilot-instructions.md
 Copilot verified via Copilot Chat test question
 prompts/ library started (optional)