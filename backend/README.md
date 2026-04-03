# Backend Services - AI BA Agent

Complete FastAPI service scaffolding for AI BA Agent project with 4 independent microservices.

## Structure

```
backend/                    # Backend API Service (Port 5000)
  app/
    main.py               # FastAPI application
    routers/              # API endpoint groups
    services/             # Business logic
    models/               # SQLAlchemy ORM models
    schemas/              # Pydantic request/response schemas
  requirements.txt        # Python dependencies
  Dockerfile              # Multi-stage Docker build

auth_service/              # Auth Service (Port 5001)
  app/
    main.py               # JWT & RBAC authentication
    routers/              # Auth endpoints
    services/             # Token management, user validation
    models/               # User & role models

rag_service/               # RAG Service (Port 5002)
  app/
    main.py               # CrewAI agent orchestration
    agents/               # 7 AI agent implementations
    skills/               # Agent skills (extraction, summarization, etc.)
    services/             # LLM, embeddings, vector DB clients

gateway/                   # Nginx Gateway (Port 80/443)
  nginx.conf              # Reverse proxy configuration
  Dockerfile              # Nginx container

infra/                     # Infrastructure & Database
  docker-compose.yml      # Full stack orchestration
  migrations/
    001_initial_schema.sql # PostgreSQL schema
```

## Services

### 1. Backend API (Port 5000)
**Purpose:** Document orchestration, workflow management, approval routing

**Key Endpoints:**
- `POST /api/documents/upload` — Upload documents for processing
- `GET /api/documents/{doc_id}` — Retrieve document metadata
- `GET /api/workflow/{workflow_id}` — Get workflow status
- `GET /api/approvals/pending` — Fetch pending approvals
- `POST /api/approvals/{approval_id}/approve` — Approve document
- `POST /api/approvals/{approval_id}/reject` — Reject with feedback

### 2. Auth Service (Port 5001)
**Purpose:** JWT authentication, user management, RBAC

**Key Endpoints:**
- `POST /auth/login` — Email/password authentication
- `POST /auth/refresh` — Refresh access token
- `GET /auth/me` — Get current user profile
- `POST /auth/logout` — Logout & invalidate token
- `GET /auth/health` — Service health check

**RBAC Model:**
- Global roles: Admin, ProjectOwner
- Project-level roles: BA, PM, Business Owner, Legal, Finance, Viewer

### 3. RAG Service (Port 5002)
**Purpose:** AI agent orchestration, semantic search, document generation

**Key Endpoints:**
- `POST /rag/extract` — Data Extraction Agent
- `POST /rag/search` — RAG Knowledge Base Search
- `POST /rag/summarize` — Summarization Agent
- `POST /rag/validate` — Validation Agent
- `GET /rag/memory/{user_id}` — Memory Agent Context
- `POST /rag/security-check` — Prompt Injection Prevention
- `POST /rag/workflow/execute` — Full workflow orchestration

### 4. Gateway (Port 80/443)
**Purpose:** Nginx reverse proxy with TLS, routing, security headers

**Routes:**
- `/` → Frontend (3000)
- `/api/*` → Backend API (5000)
- `/auth/*` → Auth Service (5001)
- `/rag/*` → RAG Service (5002)

**Features:**
- SSL/TLS termination
- Rate limiting (API, upload, auth endpoints)
- Security headers (HSTS, CSP, X-Frame-Options)
- Gzip compression
- Health checks

## Getting Started

### 1. Environment Setup

```bash
cd infra/
cp ../.env.example .env
# Edit .env with your API keys and secrets
```

**Required environment variables:**
- `JWT_SECRET` — Min 32 characters for JWT signing
- `DB_PASSWORD` — PostgreSQL password
- `OPENROUTER_API_KEY` — LLM API access
- `ELEVENLABS_API_KEY` — Speech-to-text
- `QDRANT_API_KEY` — Vector DB access (if external)

### 2. Start Services

```bash
# Start all services (Docker Compose)
cd infra/
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Test APIs

```bash
# Health check
curl http://localhost/health

# Login (Auth Service)
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'

# Upload document (Backend API)
curl -X POST http://localhost/api/documents/upload \
  -F "file=@your_file.pdf"

# Search knowledge base (RAG Service)
curl -X POST http://localhost/rag/search \
  -H "Content-Type: application/json" \
  -d '{"project_id": "proj-001", "query": "requirements"}'
```

## Development

### Local Development (Without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install backend dependencies
cd backend/
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 5000

# In another terminal, install auth service dependencies
cd auth_service/
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 5001

# And RAG service
cd rag_service/
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 5002
```

### Database

PostgreSQL runs in Docker. Access it:

```bash
docker exec -it ai_ba_postgres psql -U postgres -d ai_ba_db
```

Run migrations:
```bash
docker exec -it ai_ba_postgres psql -U postgres -d ai_ba_db < infra/migrations/001_initial_schema.sql
```

### Vector Database

Qdrant runs on port 6333. Access Web UI:
- http://localhost:6333/dashboard

### Cache

Redis runs on port 6379. For local debugging:
```bash
docker exec -it ai_ba_redis redis-cli
```

## File Structure Details

### Backend API (`backend/app/`)

- **main.py** — FastAPI app initialization, health check, static routes
- **routers/** — Organize endpoints by feature (documents.py, approvals.py, workflows.py)
- **services/** — Business logic (document service, approval service, etc.)
- **models/** — SQLAlchemy ORM models (User, Document, ApprovalWorkflow, etc.)
- **schemas/** — Pydantic models (DocumentUploadRequest, ApprovalDecision, etc.)

### Auth Service (`auth_service/app/`)

- **main.py** — JWT endpoints (login, refresh, logout) + RBAC middleware
- **services/ → token_service.py** — JWT generation, validation, revocation
- **models/user.py** — User model with password hashing (bcrypt)
- **dependencies.py** — FastAPI Depends() for authentication

### RAG Service (`rag_service/app/`)

- **main.py** — Entrypoint + orchestration endpoints
- **agents/** — 7 AI agent implementations:
  - `routing_agent.py` — Request classifier
  - `extraction_agent.py` — Data extraction from text/audio
  - `rag_agent.py` — Knowledge base verification
  - `summarization_agent.py` — Document generation
  - `validation_agent.py` — Quality gate
  - `memory_agent.py` — Context management
  - `security_agent.py` — Prompt injection prevention
- **skills/** — Agent skill implementations (extract, search, verify, summarize)
- **services/** — External integrations (LLM, embeddings, vector DB, STT)

## Deployment

### Docker Compose (Development/Testing)

```bash
docker-compose up -d
```

All services auto-start with health checks and restart policies.

### Production Deployment (Railway)

1. Connect GitHub repo to Railway
2. Railway auto-detects docker-compose.yml
3. Set environment variables in Railway dashboard
4. Deploy with `git push`

## API Documentation

Each service exposes OpenAPI (Swagger) docs:

- Backend API: http://localhost:5000/docs
- Auth Service: http://localhost:5001/docs
- RAG Service: http://localhost:5002/docs

## Monitoring

### Health Checks

```bash
# Check all services
curl http://localhost/health      # Gateway
curl http://localhost:5000/health # Backend API
curl http://localhost:5001/auth/health  # Auth Service
curl http://localhost:5002/rag/health   # RAG Service
```

### Logs

```bash
# Live logs for all services
docker-compose logs -f

# Logs for single service
docker-compose logs -f backend
docker-compose logs -f auth_service
docker-compose logs -f rag_service
docker-compose logs -f gateway
```

### Database Connection

```bash
# Access PostgreSQL
docker exec -it ai_ba_postgres psql -U postgres -d ai_ba_db

# Run a query
SELECT * FROM users;
SELECT * FROM documents;
```

## Next Steps

1. **Implement routers** — Create detailed endpoint logic in `routers/` folders
2. **Add service logic** — Implement business logic in `services/` folders
3. **Connect to databases** — Use SQLAlchemy sessions in endpoints
4. **Integrate external APIs** — LLM, STT, Gmail, Google Drive
5. **Add error handling** — Custom exception classes + middleware
6. **Write tests** — pytest fixtures for each service
7. **Deploy** — Push to Railway or your cloud provider

## Common Issues

**Q: Port already in use**
```bash
docker-compose down -v  # Remove volumes
docker system prune      # Clean up unused images
```

**Q: Database connection failed**
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check logs
docker-compose logs postgres
```

**Q: LLM API calls timing out**
- Verify API keys in `.env`
- Check network connectivity
- Review rate limits in service requirements

**Q: JWT authentication failing**
- Ensure `JWT_SECRET` is set and consistent across services
- Check token expiry time
- Verify CORS headers in gateway

---

**Version:** 0.1.0  
**Last Updated:** 2026-03-14  
**Status:** MVP Phase 1
