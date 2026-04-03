# AI BA Workflow Agent

An intelligent Business Analyst (BA) workflow automation platform that combines a 7-agent AI pipeline, RAG-powered knowledge base, multi-step approval workflows, and real-time Telegram notifications — all orchestrated via a modern Next.js frontend.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Services & Ports](#services--ports)
- [API Endpoints](#api-endpoints)
- [User Roles & RBAC](#user-roles--rbac)
- [Demo Accounts](#demo-accounts)
- [AI Agent Pipeline](#ai-agent-pipeline)
- [RAG Knowledge Base](#rag-knowledge-base)
- [Approval Workflow](#approval-workflow)
- [Notifications](#notifications)
- [Development](#development)
- [Deployment](#deployment)

---

## Overview

The AI BA Workflow Agent automates the end-to-end lifecycle of Business Analysis artifacts — from raw document ingestion, through AI-assisted extraction and summarisation, to multi-role approval and final URS generation. It is designed for BA teams who need traceability, auditability and intelligent assistance without losing human oversight.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser / Client                        │
│                     Next.js  (Port 3000)                     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                  ┌───────▼────────┐
                  │  Nginx Gateway  │  Port 80
                  └───────┬────────┘
          ┌───────────────┼───────────────┐
          │               │               │
  ┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼──────────┐
  │ Auth Service │ │   Backend   │ │   RAG Service  │
  │  Port 5001   │ │  Port 5000  │ │   Port 5002    │
  └───────┬──────┘ └──────┬──────┘ └─────┬──────────┘
          │               │               │
          └───────────────▼───────────────┘
                          │
          ┌───────────────┼─────────────────┐
          │               │                 │
  ┌───────▼──────┐ ┌──────▼──────┐ ┌───────▼──────┐
  │  PostgreSQL  │ │    Redis    │ │    Qdrant    │
  │  Port 5432   │ │  Port 6379  │ │  Port 6333   │
  └──────────────┘ └─────────────┘ └──────────────┘
```

---

## Key Features

| Feature | Description |
|---|---|
| **Document Upload** | Upload files; auto-trigger speech-to-text (ElevenLabs Scribe v2) and n8n ingestion pipeline |
| **7-Agent AI Pipeline** | CrewAI-powered agents: Router, Extractor, RAG Verifier, Summariser, Validator, Memory, Security |
| **RAG Knowledge Base** | Semantic search using `sentence-transformers` + Qdrant vector store with citation support |
| **Approval Workflow** | Multi-step, multi-role approval routing with HITL triggers for high-risk content |
| **URS Generation** | Automated User Requirement Specification document generation |
| **Notifications** | Telegram Bot + n8n workflows for daily backlog scan, weekly digest, approval reminders |
| **RBAC** | Four roles (admin, BA, business_owner, IT) with stateless JWT enforcement |
| **Audit Logging** | Full audit trail for all login events, document actions, and approval decisions |

---

## Tech Stack

**Frontend**
- [Next.js 14](https://nextjs.org/) — React full-stack framework
- Bootstrap 5 — Responsive UI
- `lucide-react` — Icon library

**Backend Services**
- [FastAPI](https://fastapi.tiangolo.com/) — Python async REST APIs (Auth, Backend, RAG)
- SQLAlchemy — PostgreSQL ORM
- `passlib[bcrypt]` — Password hashing
- `python-jose` — JWT generation & verification

**AI & ML**
- [CrewAI](https://crewai.com/) — Multi-agent AI orchestration
- [sentence-transformers](https://www.sbert.net/) — Document embeddings
- OpenRouter / DeepSeek — LLM provider

**Infrastructure**
- [Docker Compose](https://docs.docker.com/compose/) — Local orchestration
- PostgreSQL 15 — Relational database
- [Qdrant](https://qdrant.tech/) — Vector store for RAG
- Redis 7 — Cache and task queuing
- Nginx — Reverse proxy / gateway

**Integrations**
- ElevenLabs Scribe v2 — Speech-to-text transcription
- Google Drive — Document storage
- Google Sheets — Backlog tracking
- Telegram Bot — Real-time notifications
- [n8n](https://n8n.io/) — Workflow automation

---

## Project Structure

```
AI-BA-Agent/
├── auth_service/          # JWT authentication & RBAC service (Port 5001)
│   └── app/
│       ├── main.py
│       ├── models/        # SQLAlchemy ORM: User, Project, AuditLog
│       ├── services/      # auth_service.py, audit_service.py
│       └── routers/
├── backend/               # Core API orchestration service (Port 5000)
│   └── app/
│       ├── main.py
│       ├── middleware/    # RBAC JWT middleware
│       └── routers/       # documents, approvals, knowledge_base, urs, projects
├── rag_service/           # Vector embedding & search service (Port 5002)
├── frontend/              # Next.js application (Port 3000)
│   ├── pages/
│   │   ├── login.tsx
│   │   ├── index.tsx      # Dashboard
│   │   └── api/auth/      # Next.js API routes (login, logout, me)
│   └── src/
│       ├── components/    # Layout, Navbar
│       ├── services/      # auth.ts API client
│       └── styles/        # login.module.css, globals.css
├── gateway/               # Nginx reverse proxy
├── infra/
│   ├── docker-compose.yml
│   ├── .env               # Local secrets (not committed)
│   └── migrations/        # PostgreSQL init SQL
├── n8n/                   # n8n workflow definitions
└── docs/                  # Architecture & design documents
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24+)
- [Docker Compose](https://docs.docker.com/compose/) v2+
- [Node.js](https://nodejs.org/) 18+ (only for local frontend development)
- Git

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/your-org/AI-BA-Agent.git
cd AI-BA-Agent
```

### 2. Configure environment variables

```bash
cp .env.example infra/.env
```

Open `infra/.env` and fill in the required values (see [Environment Variables](#environment-variables)).

At minimum set these:
```env
JWT_SECRET=your-secret-key-min-32-characters
DB_PASSWORD=your-db-password
```

### 3. Start all services

```bash
cd infra
docker compose up -d --build
```

### 4. Verify services are healthy

```bash
docker compose ps
```

All services should show `Up (healthy)`.

### 5. Open the application

Navigate to `http://localhost:3000` and log in with a [demo account](#demo-accounts).

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET` | ✅ | Secret key for JWT signing (min 32 chars) |
| `DB_PASSWORD` | ✅ | PostgreSQL password |
| `OPENROUTER_API_KEY` | ⚠️ | LLM API key for AI pipeline |
| `ELEVENLABS_API_KEY` | ⚠️ | Speech-to-text API key |
| `GOOGLE_DRIVE_FOLDER_ID` | ⚠️ | Google Drive folder for document storage |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | ⚠️ | Google service account credentials (JSON string) |
| `TELEGRAM_BOT_TOKEN` | ⚠️ | Telegram Bot token for notifications |
| `TELEGRAM_CHAT_ID` | ⚠️ | Telegram group/channel ID |
| `N8N_API_KEY` | ⚠️ | n8n API key for workflow automation |

> ⚠️ = Required only for specific features. The core application runs without them.

See `.env.example` for the full list.

---

## Services & Ports

| Service | Port | Description |
|---|---|---|
| Frontend (Next.js) | `3000` | Web UI |
| Gateway (Nginx) | `80` | Reverse proxy entry point |
| Backend API | `5000` | Document, approval, and workflow endpoints |
| Auth Service | `5001` | Login, JWT, user management |
| RAG Service | `5002` | Embedding and semantic search |
| PostgreSQL | `5432` | Relational database |
| Redis | `6379` | Cache and task queue |
| Qdrant | `6333` | Vector store |
| n8n | `5678` | Workflow automation (if enabled) |

---

## API Endpoints

### Auth Service (`/auth`)
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Authenticate and receive JWT |
| `POST` | `/auth/refresh` | Refresh access token |
| `POST` | `/auth/logout` | Invalidate session |
| `GET` | `/auth/me` | Get current user info |

### Backend API (`/api`)
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload a document |
| `GET` | `/api/documents` | List documents for a project |
| `GET` | `/api/approvals` | List pending approvals |
| `POST` | `/api/approvals/{id}/approve` | Approve a document |
| `POST` | `/api/approvals/{id}/reject` | Reject a document |
| `POST` | `/api/knowledge-base/search` | Semantic search across knowledge base |
| `GET` | `/api/knowledge-base/documents` | List embedded knowledge base documents |
| `POST` | `/api/urs/generate` | Generate URS document |
| `GET` | `/api/projects` | List accessible projects |

---

## User Roles & RBAC

| Role | Description | Permissions |
|---|---|---|
| `admin` | System administrator | Full access to all features and user management |
| `ba` | Business Analyst | Upload documents, run AI pipeline, generate URS |
| `business_owner` | Stakeholder / approver | Review and approve/reject documents |
| `it` | IT reviewer | Read-only access to technical requirements |

Access is enforced stateless via JWT claims — the `role` and `projects` fields are embedded in the token and verified on every request by the RBAC middleware in `backend/app/middleware/rbac.py`.

---

## Demo Accounts

Use the following accounts for local testing (password: `password123`):

| Email | Role |
|---|---|
| `admin@ai-ba.local` | admin |
| `ba1@ai-ba.local` | ba |
| `ba2@ai-ba.local` | ba |
| `owner@ai-ba.local` | business_owner |

---

## AI Agent Pipeline

The 7-agent CrewAI pipeline is triggered after a document has been uploaded and transcribed:

```
Document Upload
     │
     ▼
1. Router Agent      → Classifies document type and selects downstream agents
     │
     ▼
2. Extractor Agent   → Extracts structured requirements from raw text
     │
     ▼
3. RAG Verifier      → Cross-checks extracted data against knowledge base
     │
     ▼
4. Summariser Agent  → Generates concise requirement summary
     │
     ▼
5. Validator Agent   → Validates completeness and consistency
     │
     ▼
6. Memory Agent      → Persists key facts for future sessions
     │
     ▼
7. Security Agent    → Screens for prompt injection and policy violations
     │
     ▼
   URS Draft Generated → Approval Workflow Triggered
```

---

## RAG Knowledge Base

Documents are embedded using `sentence-transformers/all-MiniLM-L6-v2` and stored in **Qdrant**. Features:

- Cosine similarity semantic search
- Re-ranking for top-k results
- Source citation with document name, section, and page reference
- Project-scoped filtering (users only search docs within their project)
- Search latency target: < 500ms for 95th percentile

---

## Approval Workflow

Multi-step approval routing based on user role:

```
BA submits document
       │
       ▼
  BA Review (self)
       │
       ▼
  Business Owner Review ──── HITL trigger if high-risk content detected
       │
       ▼
  IT Review (if required)
       │
       ▼
  Approved / Rejected (with comment & audit log)
```

Every approval decision is recorded in the `audit_logs` PostgreSQL table with actor, timestamp, IP address, and before/after values.

---

## Notifications

Three automated notification workflows powered by n8n and Telegram Bot:

| Workflow | Trigger | Description |
|---|---|---|
| **Approval Reminder** | On approval request | Notifies approvers immediately via Telegram |
| **Daily Backlog Scan** | Cron — 9:00 AM daily | Reports all pending approvals older than 24h |
| **Weekly Digest** | Cron — Monday 8:00 AM | Summary of weekly BA activity and pipeline metrics |

---

## Development

### Run frontend locally (with hot-reload)

```bash
cd frontend
npm install
npm run dev
```

### Run backend locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 5000
```

### Run auth service locally

```bash
cd auth_service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 5001
```

---

## Deployment

This project is structured for deployment on [Railway](https://railway.app/). Each service has its own `Dockerfile` and can be deployed independently.

**Deployment order:**
1. PostgreSQL → Qdrant → Redis (databases)
2. Auth Service → Backend → RAG Service (backends)
3. Frontend → Gateway

See `infra/STARTUP_GUIDE.md` and `infra/DEPLOYMENT_FILES.md` for full production deployment instructions.

---

## License

This project is for internal use. Contact the project owner for licensing terms.
