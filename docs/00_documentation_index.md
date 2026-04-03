# Technical Documentation Index
**Version:** 1.0  
**Date:** 2026-03-15  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Phase:** MVP Phase 1

---

## 📚 Document Map

This index provides quick navigation to all technical documentation for the AI Business Assistant project.

---

## 1. Core Architecture Documents

### 1.1 System Architecture & Design
**[Read: 01_system_architecture.md](../01_system_architecture.md)**

- **Purpose:** High-level system design and component relationships
- **Audience:** Architects, Tech Leads, New Team Members
- **Contents:**
  - System overview diagram
  - Service architecture (Frontend, Backend, RAG, Gateway)
  - Data flow diagrams
  - Technology stack decisions
  - Scalability considerations

**When to use:**
- Understanding how components interact
- Planning integration points
- Onboarding new developers
- Architecture review meetings

---

### 1.2 Dependency Versions & Management
**[Read: 08_dependency_versions.md](../08_dependency_versions.md)**

- **Purpose:** Track all library versions for reproducibility
- **Audience:** Developers, DevOps Engineers
- **Contents:**
  - Backend Python packages (FastAPI, SQLAlchemy, etc.)
  - Frontend Node.js packages (React, Next.js, etc.)
  - Database versions (PostgreSQL, Qdrant, Redis)
  - Version pinning strategy
  - Upgrade procedures

**When to use:**
- Setting up development environment
- Installing dependencies
- Updating packages
- Troubleshooting version conflicts

---

## 2. API & Integration Documents

### 2.1 API Specification
**[Read: 09_api_specification.md](../09_api_specification.md)**

- **Purpose:** Complete API reference documentation
- **Audience:** Frontend Developers, Backend Developers, Integrators
- **Contents:**
  - API base URLs and standards
  - Authentication (JWT, tokens)
  - User management endpoints
  - Document upload & management
  - Query & search endpoints
  - Task management API
  - Error handling & status codes
  - Rate limiting
  - Webhook integration
  - Code examples (Python, JavaScript)

**When to use:**
- Integrating with backend APIs
- Implementing frontend API calls
- Debugging request/response issues
- Building third-party integrations

**Quick Links:**
- Authentication: Section 2
- Documents: Section 4
- Search & RAG: Section 5
- Tasks & Workflows: Section 6
- Error Codes: Section 9

---

## 3. Data & Database Documents

### 3.1 Database Schema & Data Model
**[Read: 10_database_schema.md](../10_database_schema.md)**

- **Purpose:** Complete database structure and relationships
- **Audience:** Backend Developers, Database Administrators, DevOps
- **Contents:**
  - ER diagram (Entity-Relationship)
  - Core tables (Users, Documents, Queries, Tasks, etc.)
  - Supporting tables (Audit logs, API keys, Config)
  - Primary keys and foreign keys
  - Indexes and performance optimization
  - Data retention policies
  - Backup & recovery procedures
  - Sample queries & usage patterns
  - Migration strategy (Alembic)

**When to use:**
- Designing new features
- Database queries and optimization
- Understanding data relationships
- Adding new database fields
- Writing database migrations

**Key Tables:**
- `users`: User authentication & profiles
- `documents`: Uploaded documents
- `document_chunks`: Text chunks for RAG
- `queries`: User searches
- `conversations`: Chat sessions
- `tasks`: Workflow execution
- `agents`: AI agent definitions

---

## 4. Operations & DevOps Documents

### 4.1 DevOps & Deployment Guide
**[Read: 11_devops_deployment.md](../11_devops_deployment.md)**

- **Purpose:** Container setup, deployment, and infrastructure
- **Audience:** DevOps Engineers, System Administrators, Developers
- **Contents:**
  - Deployment architecture diagram
  - Docker & Docker Compose configuration
  - Dockerfile for each service
  - Nginx gateway configuration
  - Environment variable setup
  - Deployment steps (dev, staging, production)
  - Health checks & monitoring
  - Logging & log management
  - Scaling & performance tuning
  - Backup & disaster recovery
  - Security checklist

**When to use:**
- First-time setup
- Deploying to new environment
- Configuring production
- Monitoring system health
- Disaster recovery scenarios

**Critical Files:**
- `docker-compose.yml`: Container orchestration
- `.env.production`: Production settings
- `gateway/nginx.conf`: Reverse proxy config
- `infra/health_check.sh`: Health monitoring

---

### 4.2 Troubleshooting Guide & Runbook
**[Read: 14_troubleshooting_runbook.md](../14_troubleshooting_runbook.md)**

- **Purpose:** Problem diagnosis and resolution procedures
- **Audience:** All technical team members, Support Team
- **Contents:**
  - Quick diagnostic checklist
  - Common issues with solutions:
    - Service startup problems
    - Database connection issues
    - Network connectivity
    - Authentication errors
    - API response issues
    - Document processing errors
    - Search & RAG problems
    - Memory & performance issues
    - Redis connection issues
    - Qdrant vector DB problems
  - Monitoring metrics & alerting
  - Recovery procedures
  - Performance tuning tips
  - Emergency contacts & escalation

**When to use:**
- System is down or malfunctioning
- Users report errors
- Performance degradation
- Unexpected behavior
- Need to recover from backup

**Quick Lookup:**
- Service won't start → Section 2.1
- Database errors → Section 2.2
- Network problems → Section 2.3
- API timeouts → Section 2.5
- Document processing stuck → Section 2.6
- Search returns nothing → Section 2.7

---

## 5. Testing & Quality Documents

### 5.1 Testing & QA Guide
**[Read: 12_testing_qa.md](../12_testing_qa.md)**

- **Purpose:** Testing strategy, test cases, and QA procedures
- **Audience:** QA Engineers, Developers, Test Automation Engineers
- **Contents:**
  - Test strategy & pyramid
  - Unit testing (pytest, Jest)
  - Integration testing
  - End-to-end testing (Cypress)
  - Smoke testing procedures
  - Performance testing (Locust)
  - CI/CD pipeline configuration
  - Test fixtures & data management
  - Code coverage targets
  - Test reporting & metrics

**When to use:**
- Writing test cases
- Setting up automated testing
- Preparing for release
- Debugging test failures
- Measuring code quality

**Test Frameworks:**
- Backend: pytest (Python)
- Frontend: Jest + React Testing Library (JavaScript)
- E2E: Cypress / Playwright
- Load: Locust

---

## 6. Planning & Project Documents

### 6.1 Implementation Roadmap
**[Read: 13_implementation_roadmap.md](../13_implementation_roadmap.md)**

- **Purpose:** Sprint planning, timeline, and deliverables
- **Audience:** Project Manager, Tech Leads, Stakeholders
- **Contents:**
  - Project timeline (24 weeks)
  - Phase 1: MVP (Weeks 1-12)
  - Phase 2: Enhancement (Weeks 13-18)
  - Phase 3: Optimization (Weeks 19-24)
  - Sprint breakdown (8 sprints)
  - Task lists per sprint
  - Resource allocation
  - Risk management
  - Success metrics
  - Critical path analysis
  - Launch checklist

**Sprints in Phase 1:**
1. Foundation & Setup (Weeks 1-2)
2. Authentication (Weeks 2-3)
3. Document Upload & Processing (Weeks 3-5)
4. Search & RAG (Weeks 5-7)
5. Frontend Search UI (Weeks 7-8)
6. Multi-turn Conversations (Weeks 8-9)
7. AI Agents (Weeks 9-11)
8. Deployment & DevOps (Weeks 11-12)

---

## 7. Quick Reference Guides

### 7.1 Common Tasks

#### Setting Up Development Environment
```
1. Read: 08_dependency_versions.md (Section 10)
2. Read: 11_devops_deployment.md (Section 5.1)
3. Run: docker-compose -f docker-compose.dev.yml up -d
4. Test: ./infra/health_check.sh
```

#### Adding New API Endpoint
```
1. Read: 09_api_specification.md (understand patterns)
2. Read: 10_database_schema.md (if new table needed)
3. Create route in: backend/src/routes/
4. Add tests in: tests/integration/
5. Document in: 09_api_specification.md
```

#### Deploying to Production
```
1. Read: 11_devops_deployment.md (Section 5.2)
2. Run: docker-compose build
3. Run: docker-compose up -d
4. Run: ./infra/health_check.sh
5. Monitor: docker-compose logs -f
```

#### Troubleshooting Service Failure
```
1. Read: 14_troubleshooting_runbook.md (Section 1)
2. Run: ./infra/health_check.sh
3. Check: docker-compose logs <service>
4. Find solution in: Section 2 of troubleshooting guide
5. Escalate if needed: Section 6 (Emergency Contacts)
```

#### Writing Tests
```
1. Read: 12_testing_qa.md (appropriate section)
2. Backend: pytest framework (Section 2.1)
3. Frontend: Jest framework (Section 2.2)
4. E2E: Cypress framework (Section 4.1)
4. Run: npm test or pytest
5. Check coverage target: 85%+
```

---

### 7.2 Technology Decision Matrix

| Component | Technology | Why | Reference |
|-----------|-----------|-----|-----------|
| Backend | FastAPI Python 3.11 | Fast, async, Pythonic | 01_system_architecture.md |
| Frontend | React + Next.js 14 | SSR, performance | 01_system_architecture.md |
| Database | PostgreSQL 15 | ACID, reliability | 10_database_schema.md |
| Vector DB | Qdrant | Semantic search | 01_system_architecture.md |
| Cache | Redis | Session storage | 11_devops_deployment.md |
| Gateway | Nginx | Load balancing | 11_devops_deployment.md |
| LLM | GPT-4-turbo via OpenRouter | Best quality/cost | 09_api_specification.md |
| Testing | pytest + Jest + Cypress | Industry standard | 12_testing_qa.md |

---

## 8. Status by Document

| Document | Status | Last Updated | Completeness |
|----------|--------|--------------|--------------|
| [01_system_architecture.md](../01_system_architecture.md) | ✅ Done | 2026-03-15 | 100% |
| [08_dependency_versions.md](../08_dependency_versions.md) | ✅ Done | 2026-03-15 | 100% |
| [09_api_specification.md](../09_api_specification.md) | ✅ Done | 2026-03-15 | 100% |
| [10_database_schema.md](../10_database_schema.md) | ✅ Done | 2026-03-15 | 100% |
| [11_devops_deployment.md](../11_devops_deployment.md) | ✅ Done | 2026-03-15 | 100% |
| [12_testing_qa.md](../12_testing_qa.md) | ✅ Done | 2026-03-15 | 100% |
| [13_implementation_roadmap.md](../13_implementation_roadmap.md) | ✅ Done | 2026-03-15 | 100% |
| [14_troubleshooting_runbook.md](../14_troubleshooting_runbook.md) | ✅ Done | 2026-03-15 | 100% |

---

## 9. Document Usage by Role

### 👨‍💼 Project Manager
**Essential Reading:**
1. [13_implementation_roadmap.md](../13_implementation_roadmap.md) - Full timeline & sprints
2. [01_system_architecture.md](../01_system_architecture.md) - Compare with requirements

**Reference:**
- Track sprint progress against roadmap
- Identify critical paths and blockers
- Monitor resource allocation

---

### 👨‍💻 Backend Developer
**Essential Reading:**
1. [09_api_specification.md](../09_api_specification.md) - API contracts
2. [10_database_schema.md](../10_database_schema.md) - Database design
3. [08_dependency_versions.md](../08_dependency_versions.md) - Dependency setup

**Reference:**
- [11_devops_deployment.md](../11_devops_deployment.md) - Deployment
- [12_testing_qa.md](../12_testing_qa.md) - Testing requirements
- [14_troubleshooting_runbook.md](../14_troubleshooting_runbook.md) - Debugging

---

### 👨‍🎨 Frontend Developer
**Essential Reading:**
1. [09_api_specification.md](../09_api_specification.md) - API endpoints & responses
2. [01_system_architecture.md](../01_system_architecture.md) - Component structure
3. [08_dependency_versions.md](../08_dependency_versions.md) - Package versions

**Reference:**
- [12_testing_qa.md](../12_testing_qa.md) - Component testing
- [11_devops_deployment.md](../11_devops_deployment.md) - Build & deployment
- [14_troubleshooting_runbook.md](../14_troubleshooting_runbook.md) - Network issues

---

### 🔧 DevOps Engineer
**Essential Reading:**
1. [11_devops_deployment.md](../11_devops_deployment.md) - Complete guide
2. [14_troubleshooting_runbook.md](../14_troubleshooting_runbook.md) - Monitoring & recovery
3. [08_dependency_versions.md](../08_dependency_versions.md) - Version management

**Reference:**
- [10_database_schema.md](../10_database_schema.md) - Backup procedures
- [13_implementation_roadmap.md](../13_implementation_roadmap.md) - Release planning

---

### 🧪 QA Engineer
**Essential Reading:**
1. [12_testing_qa.md](../12_testing_qa.md) - Test strategy & procedures
2. [09_api_specification.md](../09_api_specification.md) - API behavior
3. [14_troubleshooting_runbook.md](../14_troubleshooting_runbook.md) - System diagnosis

**Reference:**
- [10_database_schema.md](../10_database_schema.md) - Data relationships
- [13_implementation_roadmap.md](../13_implementation_roadmap.md) - Feature timeline

---

### 👨‍🔬 Solution Architect
**Essential Reading:**
1. [01_system_architecture.md](../01_system_architecture.md) - Full architecture
2. [13_implementation_roadmap.md](../13_implementation_roadmap.md) - Phased delivery
3. [08_dependency_versions.md](../08_dependency_versions.md) - Technology choices

**Reference:**
- [11_devops_deployment.md](../11_devops_deployment.md) - Infrastructure design
- [10_database_schema.md](../10_database_schema.md) - Data model design

---

## 10. Cross-Reference Matrix

### Finding Information

**Question:** How do I...?

| Question | Answer | Document | Section |
|----------|--------|----------|---------|
| Set up development environment? | Docker setup + dependencies | 11_devops_deployment.md, 08_dependency_versions.md | 5.1, 10 |
| Understand system components? | Architecture & data flow | 01_system_architecture.md | 1-3 |
| Call the API? | Endpoint reference | 09_api_specification.md | 3-8 |
| Add new database field? | Schema modification | 10_database_schema.md | 6 |
| Write tests? | Testing frameworks & examples | 12_testing_qa.md | 2-4 |
| Deploy to production? | Deployment procedures | 11_devops_deployment.md | 5.2 |
| Fix service failure? | Troubleshooting steps | 14_troubleshooting_runbook.md | 2 |
| Plan next sprint? | Sprint roadmap | 13_implementation_roadmap.md | 2-8 |
| Monitor health? | Health checks & metrics | 14_troubleshooting_runbook.md | 3-4 |
| Understand dependencies? | Version & package info | 08_dependency_versions.md | 1-11 |

---

## 11. Update Schedule

### Document Maintenance Cycle

```
Daily:     Troubleshooting guide (add new issues)
Weekly:    Implementation roadmap (sprint updates)
Monthly:   All technical docs (version updates)
Quarterly: Architecture (major changes)
Annually:  Full documentation review
```

### How to Update Documentation

1. **Minor Updates:** Direct edits with git comment
2. **Major Updates:** Create PR, review, then merge
3. **New Documents:** Follow existing template structure
4. **Deprecations:** Mark with ⚠️ WARNING banner

---

## 12. Document Templates

### Adding New Section to Existing Document

```markdown
### X.Y New Section Title

**Purpose:** Brief description  
**Audience:** Target readers  

**Contents:**
- Bullet point 1
- Bullet point 2

**When to use:**
- Use case 1
- Use case 2
```

### Creating New Document

```markdown
# Document Title
**Version:** 1.0  
**Date:** YYYY-MM-DD  
**Project:** AI 智能業務助理  
**Phase:** MVP Phase 1

---

## 1. Introduction

## 2. Main Content

---

## END OF [DOCUMENT NAME]
```

---

## 13. Support & Contact

### Documentation Issues

- **Report Bug:** [GitHub Issues](issues)
- **Request Update:** [Pull Request](pulls)
- **Ask Question:** [Discussions](discussions)

### Technical Support

- **Backend Issues:** Backend Lead
- **Frontend Issues:** Frontend Lead
- **DevOps Issues:** DevOps Lead
- **All Issues:** Support Channel

---

## END OF TECHNICAL DOCUMENTATION INDEX

---

**Last Updated:** 2026-03-15  
**Next Review:** 2026-04-15  
**Document Status:** Complete & Ready for Use
