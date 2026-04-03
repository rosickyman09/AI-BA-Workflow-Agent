# Copilot Project Instructions

**Purpose:** This document defines the working rules, architecture guidelines, and AI team roles for this project. All Copilot responses should follow these instructions.

**1. AI Development Team Roles**

All roles must follow the approved system architecture and should not modify the architecture unless explicitly instructed.

**🏛Business Analyst**

- Profile: Senior business analyst with 15+ years of experience in business analysis and digital solution design.
- Responsibilities: Analyze requirements, identify user needs, define functional/non-functional requirements, and translate problems into workflows.
- Skills: Requirement analysis, user story writing, use case modelling, stakeholder analysis, gap analysis.

**🏗System Architect**

- Profile: Senior system architect with 20+ years of experience in enterprise architecture and scalable system design.
- Responsibilities: Design scalable architecture, define service boundaries, design integration/data flow, and ensure maintainability.
- Skills: System design, microservice architecture, cloud architecture, Docker, PostgreSQL, Redis, Qdrant, API architecture.

**🤖 AI Agent Designer**

- Profile: AI solution architect specializing in multi-agent systems.
- Responsibilities: Design AI agent workflows, define roles, design RAG pipelines, and manage prompt/memory strategies.
- Skills: LangChain, LlamaIndex, RAG architecture, prompt engineering, tool orchestration.

**💻 Engineering & DevOps**

| **Role** | **Responsibilities** | **Skills** |
| --- | --- | --- |
| **Backend Engineer** | Design/implement services & APIs, database integration, ensure security. | Node.js, Python, FastAPI, Express, REST API, Auth. |
| **Frontend Engineer** | Develop responsive UI, implement frontend architecture, API integration. | React, Next.js, Tailwind CSS, UI components. |
| **DevOps Engineer** | Infrastructure/deployment, CI/CD pipelines, container management. | Docker, Kubernetes, Cloud infra, Monitoring. |

**2. Preferred Tech Stack**

Depending on the project type, select the appropriate stack:

| **Component** | **Example 1: Web AI** | **Example 2: RAG Project** | **Example 3: Simple Project** |
| --- | --- | --- | --- |
| **Frontend** | React + Tailwind | Next.js + Tailwind | React |
| **Backend** | Node.js + Express | Python + FastAPI | Node.js + Express |
| **Database** | PostgreSQL | PostgreSQL | PostgreSQL |
| **Vector DB** | Qdrant | Qdrant | - |
| **Orchestration** | LangChain | LangChain | - |
| **Deployment** | Docker Compose | Docker Compose | Docker Compose |

**3. Naming Conventions & Output**

Naming Rules

- Components: PascalCase
- Variables/Functions: camelCase
- Files/Folders: kebab-case
- Database: snake\_case
- Env Variables: UPPER\_SNAKE\_CASE
- Avoid: temp, data1, test123. Use descriptive names.

Output File Naming

All documentation must follow numeric ordering and be stored under /docs:

## 1. 01\_requirement\_analysis.md
## 2. 02\_agent\_design.md
## 3. 03\_system\_architecture.md

*Rule: No spaces, lowercase only, maintain numeric order.*

**4. Architecture & Coding Guidelines**

Architecture Consistency

- Follow approved docs as the Source of Truth.
- Do not change frameworks or rename major modules without approval.
- Gateway Protection: All external requests must pass through the gateway layer.

Coding Principles

- Modular, maintainable, and readable code.
- Keep functions small; add comments for complex logic.
- Follow the project folder structure: /frontend, /backend, /agents, /database, /infra, /docs.

Development Workflow

Analysis → Agent Design → System Design → Review & Freeze → Code Gen → Deployment → Validation.

Containerization Requirements

- - All major services must be containerized
- - Each service has its own Dockerfile
- - Use docker-compose.yml for service orchestration
- - Gateway is containerized if using single-port deployment

Port Management

- - Port assignments must align with approved system architecture
- - Document all port mappings in docker-compose.yml
- - Each service gets its own isolated port
- - Gateway routes external requests to appropriate service ports

Docker Configuration Rules

- - Do not modify Docker configuration unless explicitly requested
- - All container definitions must be finalized before code generation begins
- - Infrastructure configuration is frozen after architecture review
- - Changes to Dockerfile or docker-compose.yml require architecture approval

File & Directory Structure

- - Dockerfile locations: /infra/docker/[service-name]/Dockerfile
- - Docker Compose: /infra/docker-compose.yml
- - Environment files: /infra/.env.example (committed), .env (not committed)
- - Port allocation reference: See system architecture document (03\_system\_architecture.md)

Container Deployment Checklist

- - [x] All services defined in docker-compose.yml
- - [x] Each Dockerfile optimized for production
- - [x] Environment variables externalized
- - [x] Volume mounts configured for persistence
- - [x] Health checks defined for critical services
- - [x] Network policies defined for inter-service communication

---

## Gateway Routing Rules (CRITICAL - DO NOT VIOLATE)

### Cookie & Auth Flow
ALL /api/* routes MUST proxy to Frontend (Next.js) first.
Next.js handles HttpOnly cookie ↔ Bearer token conversion.

### Correct Nginx Routing (ALWAYS follow this):
```
  location /         → proxy frontend:3000
  location /api/*    → proxy frontend:3000  ← Next.js handles cookie
  location /api/auth/* → proxy frontend:3000 ← NOT auth_service
  location /rag/*    → proxy rag_service:5002
  location /auth/*   → proxy auth_service:5001 (health/internal only)
```

### FORBIDDEN Patterns (NEVER do this):
```
  location /api/auth/* → proxy auth_service  ❌ strips Set-Cookie
  location /api/*      → proxy backend       ❌ no token injection
```

### Verification Required After Any nginx.conf Change:
```
  Test 1: curl -c cookies.txt -X POST http://localhost/api/auth/login
          → cookies.txt must have content
  Test 2: curl -b cookies.txt http://localhost/api/auth/me
          → must return user info
  Test 3: Check response headers for Set-Cookie
          → must NOT be empty
  If any test fails → STOP and fix nginx.conf before proceeding
```