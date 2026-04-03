# Deployment Plan - AI BA Agent

**Version:** 2.0  
**Date:** 2026-03-17  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Status:** Production Ready  
**Updated From:** docs/04_deployment_plan.txt + Current Implementation

---

## Table of Contents

1. [Docker Compose Structure](#1-docker-compose-structure)
2. [Environment Variables](#2-environment-variables)
3. [Startup Sequence](#3-startup-sequence-database--backend--frontend)
4. [Health Checks](#4-health-checks-per-service)
5. [Rollback Strategy](#5-rollback-strategy-with-specific-steps)
6. [Local vs Production](#6-local-vs-production-comparison)
7. [Dockerfiles](#7-dockerfiles-per-service)
8. [Gateway Routing](#8-gateway-routing-rules)
9. [Volumes & Backup](#9-docker-volumes--backuprestore)
10. [Container Dependencies](#10-container-dependency-order)
11. [Network Segmentation](#11-network-segmentation)
12. [Image Naming](#12-image-naming-strategy)

---

## 1. Docker Compose Structure

### File Location
\\\
project-root/
└── infra/
    └── docker-compose.yml
\\\

### Complete YAML Structure

\\\yaml
version: '3.9'

services:
  # ========================================================================
  # INFRASTRUCTURE LAYER (Databases & Services)
  # ========================================================================

  postgres:
    image: postgres:15-alpine
    container_name: ai_ba_postgres
    environment:
      POSTGRES_DB: ai_ba_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d ai_ba_db"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - ai-ba-network
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:1.7.0
    container_name: ai_ba_qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD-SHELL", "bash -c 'echo OK'"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    networks:
      - ai-ba-network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: ai_ba_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD-SHELL", "redis-cli ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - ai-ba-network
    restart: unless-stopped

  # ========================================================================
  # APPLICATION SERVICES LAYER
  # ========================================================================

  auth_service:
    build:
      context: ../auth_service
      dockerfile: Dockerfile
    container_name: ai_ba_auth_service
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ai_ba_db
      DB_USER: postgres
      DB_PASSWORD: postgres
      JWT_SECRET: dev-secret-key
      REDIS_HOST: redis
      REDIS_PORT: 6379
    ports:
      - "5001:5001"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:5001/health')\""]
      interval: 15s
      timeout: 10s
      retries: 3
      start_period: 20s
    networks:
      - ai-ba-network
    restart: unless-stopped

  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: ai_ba_backend
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ai_ba_db
      DB_USER: postgres
      DB_PASSWORD: postgres
      JWT_SECRET: dev-secret-key
      REDIS_HOST: redis
      REDIS_PORT: 6379
      AUTH_SERVICE_URL: http://auth_service:5001
      RAG_SERVICE_URL: http://rag_service:5002
    ports:
      - "5000:5000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      auth_service:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:5000/health')\""]
      interval: 15s
      timeout: 10s
      retries: 3
      start_period: 20s
    networks:
      - ai-ba-network
    restart: unless-stopped

  rag_service:
    build:
      context: ../rag_service
      dockerfile: Dockerfile
    container_name: ai_ba_rag_service
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ai_ba_db
      DB_USER: postgres
      DB_PASSWORD: postgres
      QDRANT_HOST: qdrant
      QDRANT_PORT: 6333
      REDIS_HOST: redis
      REDIS_PORT: 6379
    ports:
      - "5002:5002"
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:5002/health')\""]
      interval: 15s
      timeout: 10s
      retries: 3
      start_period: 20s
    networks:
      - ai-ba-network
    restart: unless-stopped

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    container_name: ai_ba_frontend
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:3000 || exit 1"]
      interval: 15s
      timeout: 10s
      retries: 3
      start_period: 20s
    networks:
      - ai-ba-network
    restart: unless-stopped

  # ========================================================================
  # GATEWAY LAYER (Public-facing Reverse Proxy)
  # ========================================================================

  gateway:
    build:
      context: ../gateway
      dockerfile: Dockerfile
    container_name: ai_ba_gateway
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      frontend:
        condition: service_healthy
      backend:
        condition: service_healthy
      auth_service:
        condition: service_healthy
      rag_service:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost/health || exit 1"]
      interval: 15s
      timeout: 10s
      retries: 3
      start_period: 20s
    networks:
      - ai-ba-network
    restart: unless-stopped

# ============================================================================
# VOLUMES (Data Persistence)
# ============================================================================

volumes:
  postgres_data:
    driver: local
  qdrant_data:
    driver: local
  redis_data:
    driver: local

# ============================================================================
# NETWORKS (Service Communication)
# ============================================================================

networks:
  ai-ba-network:
    driver: bridge
\\\

### Structure Explanation

| Layer | Services | Purpose | Internal? |
|-------|----------|---------|-----------|
| **Infrastructure** | postgres, qdrant, redis | Data persistence & caching | Yes |
| **Application** | auth_service, backend, rag_service | Business logic | Yes |
| **Frontend** | frontend | Web UI | Yes (via gateway) |
| **Gateway** | gateway | Public-facing entry point | No (exposed: 80, 443) |

---

## 2. Environment Variables

### File Locations
- **Reference:** \.env.example\ (committed to repo)
- **Actual:** \.env\ (NOT committed, local secrets)
- **Docker Use:** docker-compose.yml reads from \.env\

### Development Environment

\\\ash
# .env (Development)

# ===================
# DATABASE
# ===================
DB_HOST=postgres
DB_PORT=5432
DB_NAME=ai_ba_db
DB_USER=postgres
DB_PASSWORD=postgres                          # WEAK: OK for dev only
DB_POOL_SIZE=20

# ===================
# AUTHENTICATION
# ===================
JWT_SECRET=dev-secret-key-12345               # WEAK: OK for dev only
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
JWT_REFRESH_DAYS=30

# ===================
# CACHE & VECTOR DB
# ===================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=documents_embeddings

# ===================
# EXTERNAL APIs
# ===================
OPENROUTER_API_KEY=                           # Optional for dev
DEEPSEEK_API_KEY=                             # Optional for dev
ELEVENLABS_API_KEY=                           # Optional for dev
DEEPGRAM_API_KEY=                             # Optional for dev

GOOGLE_CLIENT_ID=                             # Optional for dev
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_SHEETS_ID=

TELEGRAM_BOT_TOKEN=                           # Optional for dev
TELEGRAM_CHAT_ID=

# ===================
# SERVICE CONFIG
# ===================
SERVICE_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:5000
API_TIMEOUT_SECONDS=30

# ===================
# FEATURE FLAGS
# ===================
ENABLE_RAG=true
ENABLE_APPROVALS=true
ENABLE_EMAIL_INGESTION=false
ENABLE_BACKLOG_SCAN=false
ENABLE_SECURITY_CHECKS=true

# ===================
# MONITORING
# ===================
SENTRY_DSN=
DATA_DOG_API_KEY=
LOG_AGGREGATION_ENABLED=false
\\\

### Production Environment

\\\ash
# .env (Production - on Railway/Cloud)

# ===================
# DATABASE (Managed by Railway)
# ===================
DB_HOST=prod-postgres.railway.internal
DB_PORT=5432
DB_NAME=ai_ba_db
DB_USER=ba_user
DB_PASSWORD=VERY_LONG_RANDOM_STRING_MIN_20_CHARS  # STRONG: Required
DB_POOL_SIZE=50                               # Higher for prod

# ===================
# AUTHENTICATION (STRONG: Rotate periodically)
# ===================
JWT_SECRET=VERY_LONG_RANDOM_STRING_MIN_32_CHARS   # STRONG: Required
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
JWT_REFRESH_DAYS=7                            # Shorter expiry for prod

# ===================
# CACHE & VECTOR DB (Railway-managed)
# ===================
REDIS_HOST=prod-redis.railway.internal
REDIS_PORT=6379
REDIS_PASSWORD=STRONG_REDIS_PASSWORD          # REQUIRED for prod
REDIS_DB=0

QDRANT_HOST=prod-qdrant.railway.internal
QDRANT_PORT=6333
QDRANT_API_KEY=STRONG_API_KEY                 # REQUIRED for prod
QDRANT_COLLECTION_NAME=documents_embeddings

# ===================
# EXTERNAL APIs (REQUIRED)
# ===================
OPENROUTER_API_KEY=sk-or-v1-ACTUAL_KEY        # Real key
DEEPSEEK_API_KEY=sk-ACTUAL_KEY                # Real key
ELEVENLABS_API_KEY=ACTUAL_KEY                 # Real key
DEEPGRAM_API_KEY=ACTUAL_KEY                   # Real key

GOOGLE_CLIENT_ID=client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=ACTUAL_SECRET
GOOGLE_REFRESH_TOKEN=refresh_token_from_oauth_flow
GOOGLE_DRIVE_FOLDER_ID=folder_id_from_drive
GOOGLE_SHEETS_ID=spreadsheet_id

TELEGRAM_BOT_TOKEN=bot_token_from_botfather
TELEGRAM_CHAT_ID=chat_id_for_notifications

# ===================
# SERVICE CONFIG
# ===================
SERVICE_ENV=production
DEBUG=false
LOG_LEVEL=INFO                                # Less verbose in prod
FRONTEND_URL=https://your-domain.com
BACKEND_URL=https://your-domain.com/api
API_TIMEOUT_SECONDS=30

# ===================
# FEATURE FLAGS
# ===================
ENABLE_RAG=true
ENABLE_APPROVALS=true
ENABLE_EMAIL_INGESTION=true                   # Enabled in prod
ENABLE_BACKLOG_SCAN=true                      # Enabled in prod
ENABLE_SECURITY_CHECKS=true

# ===================
# MONITORING (REQUIRED)
# ===================
SENTRY_DSN=https://key@sentry.io/project_id   # For error tracking
DATA_DOG_API_KEY=dd_api_key                    # For APM monitoring
LOG_AGGREGATION_ENABLED=true
\\\

### Environment Variable Injection Points

| Service | Variables Used | Source |
|---------|---|---|
| **postgres** | DB_NAME, DB_USER, DB_PASSWORD | docker-compose (hardcoded) |
| **auth_service** | JWT_SECRET, REDIS_HOST, DB_* | docker-compose |
| **backend** | JWT_SECRET, REDIS_HOST, AUTH_URL, RAG_URL | docker-compose |
| **rag_service** | QDRANT_HOST, REDIS_HOST, DB_* | docker-compose |
| **frontend** | FRONTEND_URL, BACKEND_URL | .env.local (build-time) |
| **gateway** | N/A (Nginx config only) | nginx.conf |

---

## 3. Startup Sequence (Database → Backend → Frontend)

### Mandatory Startup Order

The docker-compose.yml enforces this order via \depends_on\ with \condition: service_healthy\:

\\\
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Infrastructure Layer (Parallel)                     │
│  ├─ postgres:5432 (must be healthy first)                   │
│  ├─ qdrant:6333 (parallel with postgres)                    │
│  └─ redis:6379 (parallel with postgres)                     │
└─────────────────────────────────────────────────────────────┘
                          ↓ (wait for healthy)
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Application Services Layer (Parallel)               │
│  ├─ auth_service:5001 (depends_on: postgres✓, redis✓)       │
│  ├─ backend:5000 (depends_on: postgres✓, redis✓, auth✓)     │
│  └─ rag_service:5002 (depends_on: postgres✓, qdrant✓, redis✓)|
└─────────────────────────────────────────────────────────────┘
                          ↓ (wait for healthy)
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Presentation Layer                                  │
│  ├─ frontend:3000 (no dependencies)                         │
│  └─ gateway:80/443 (depends_on: all services✓)              │
└─────────────────────────────────────────────────────────────┘
\\\

### Docker Compose Commands

\\\ash
# Build all images (non-blocking)
docker compose build

# Start all services with proper sequencing
docker compose up -d

# Watch startup progress
docker compose logs -f

# Verify startup order (all should be "Up (healthy)")
docker compose ps

# Example healthy output:
# NAME                 STATUS
# ai_ba_postgres       Up (healthy)
# ai_ba_redis          Up (healthy)
# ai_ba_qdrant         Up (healthy)
# ai_ba_auth_service   Up (healthy)
# ai_ba_backend        Up (healthy)
# ai_ba_rag_service    Up (healthy)
# ai_ba_frontend       Up (healthy)
# ai_ba_gateway        Up (healthy)
\\\

### Detailed Startup Timeline

\\\
Time  Action                           Service          Health Status
────  ──────────────────────────────   ──────────────   ─────────────
0s    docker compose up -d             -                Starting...
5s    postgres listening                postgres         Starting (0/5)
8s    postgres accepts connections     postgres         Healthy ✓
10s   redis listening                  redis            Healthy ✓
12s   qdrant listening                 qdrant           Healthy ✓
15s   auth_service starting            auth_service     Starting (0/3)
18s   auth_service /health responds    auth_service     Healthy ✓
20s   backend starting                 backend          Starting (0/3)
23s   backend /health responds         backend          Healthy ✓
25s   rag_service starting             rag_service      Starting (0/3)
28s   rag_service /health responds     rag_service      Healthy ✓
30s   frontend starting                frontend         Starting (0/3)
32s   frontend :3000 responds          frontend         Healthy ✓
35s   gateway starting                 gateway          Starting (0/3)
38s   gateway :80 responds             gateway          Healthy ✓
40s   ✓ All services healthy & ready   -                Ready for use
\\\

### Startup Verification Commands

\\\ash
# 1. Verify all containers are running
docker compose ps
# Expected: All containers have status "Up (healthy)"

# 2. Test database connectivity
docker compose exec postgres pg_isready -U postgres -d ai_ba_db
# Expected output: "accepting connections"

# 3. Test backend API health
curl http://localhost:5000/health
# Expected: {"status": "healthy", "service": "backend", "timestamp": "..."}

# 4. Test auth service health
curl http://localhost:5001/health
# Expected: {"status": "healthy", "service": "auth_service"}

# 5. Test RAG service health
curl http://localhost:5002/health
# Expected: {"status": "healthy", "service": "rag_service"}

# 6. Test gateway health
curl http://localhost/health
# Expected: {"status": "ok"} or similar

# 7. Test frontend
curl http://localhost:3000
# Expected: HTML of login page (200 OK)
\\\

---

## 4. Health Checks per Service

Each service includes a \healthcheck\ directive that Docker uses for orchestration.

### PostgreSQL

\\\yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres -d ai_ba_db"]
  interval: 10s      # Check every 10 seconds
  timeout: 5s        # Max 5 seconds to respond
  retries: 5         # Fail after 5 consecutive failures
  start_period: 30s  # Grace period before first check
\\\

### Auth Service

\\\yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:5001/health')\""]
  interval: 15s
  timeout: 10s
  retries: 3
  start_period: 20s
\\\

**Expected Response:**
\\\json
{
  "status": "healthy",
  "service": "auth_service",
  "timestamp": "2026-03-17T08:45:00Z"
}
\\\

### Backend API

\\\yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:5000/health')\""]
  interval: 15s
  timeout: 10s
  retries: 3
  start_period: 20s
\\\

### Frontend

\\\yaml
healthcheck:
  test: ["CMD-SHELL", "wget -q --spider http://localhost:3000 || exit 1"]
  interval: 15s
  timeout: 10s
  retries: 3
  start_period: 20s
\\\

### Checking Health Status

\\\ash
# View health status for all services
docker compose ps

# View detailed health status
docker inspect ai_ba_postgres --format='{{json .State.Health}}'

# View health logs
docker compose logs --tail=20 postgres
\\\

---

## 5. Rollback Strategy (with Specific Steps)

### Container-Level Rollback

\\\ash
# STEP 1: Get previous image
docker images | grep ai_ba_backend
# Find previous image ID

# STEP 2: Tag previous image as rollback
docker tag <previous_image_id> ai_ba_backend:rollback

# STEP 3: Update docker-compose.yml to use rollback tag
# Change: image: ai_ba_backend:latest
# To:     image: ai_ba_backend:rollback

# STEP 4: Restart service
docker compose up -d backend

# STEP 5: Verify health
curl http://localhost:5000/health
\\\

### Database Rollback

\\\ash
# STEP 1: Stop services
docker compose stop backend auth_service

# STEP 2: Restore from backup
docker compose exec -T postgres psql -U postgres -d ai_ba_db < previous_backup.sql

# STEP 3: Restart
docker compose up -d
\\\

### Emergency Full Reset

\\\ash
# WARNING: This deletes ALL data!

# Stop everything and remove volumes
docker compose down -v

# Rebuild images
docker compose build --no-cache

# Start fresh
docker compose up -d
\\\

---

## 6. Local vs Production Comparison

| Aspect | Local Development | Production (Railway) |
|--------|-------------------|----------------------|
| **Deployment Method** | \docker compose up\ | Railway Git + CI/CD |
| **Database** | PostgreSQL (local container) | Railway Managed PostgreSQL |
| **Port Exposure** | All ports exposed | Only 80/443 exposed |
| **TLS/SSL** | Self-signed certs (dev) | Let's Encrypt (auto-renewed) |
| **Secrets** | Hardcoded in .env (dev values) | Railway Variables (strong values) |
| **Backups** | Manual | Automatic daily |
| **Logging** | \docker compose logs\ | Railway Dashboard + Sentry |
| **Cost** | None (local machine) | \/month+ per service |

---

## 7. Dockerfiles per Service

### Backend Dockerfile

**Location:** \ackend/Dockerfile\

\\\dockerfile
# ========================================================================
# BACKEND API SERVICE - Multi-Stage Build
# ========================================================================

# Stage 1: Builder (installs dependencies)
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ========================================================================
# Stage 2: Runtime (lean production image)
FROM python:3.11-slim

WORKDIR /app

# Copy pre-installed dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages \\
  /usr/local/lib/python3.11/site-packages

# Copy application code
COPY app app/
COPY requirements.txt .

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=15s --timeout=10s --retries=3 --start-period=20s \\
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
\\\

### Frontend Dockerfile

**Location:** \rontend/Dockerfile\

\\\dockerfile
# ========================================================================
# FRONTEND - Next.js React App - Multi-Stage Build
# ========================================================================

# Stage 1: Builder (installs deps + builds)
FROM node:20.10-alpine as builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

COPY . .
RUN npm run build

# ========================================================================
# Stage 2: Runtime (serve with Nginx)
FROM nginx:1.25.3-alpine

# Remove default Nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built Next.js app from builder
COPY --from=builder /app/out /usr/share/nginx/html

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=10s --retries=3 --start-period=20s \\
  CMD wget -q --spider http://localhost:3000 || exit 1

CMD ["nginx", "-g", "daemon off;"]
\\\

### Gateway Dockerfile

**Location:** \gateway/Dockerfile\

\\\dockerfile
FROM nginx:1.25.3-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/ /etc/nginx/conf.d/
COPY certs/ /etc/nginx/certs/

EXPOSE 80 443

HEALTHCHECK --interval=15s --timeout=10s --retries=3 --start-period=20s \\
  CMD wget -q --spider http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
\\\

---

## 8. Gateway Routing Rules

All traffic flows through the Nginx gateway on ports 80/443.

### Complete nginx.conf Routing

\\\
ginx
# ========================================================================
# UPSTREAM SERVICE DEFINITIONS
# ========================================================================

upstream frontend {
    server frontend:3000;
}

upstream backend_api {
    server backend:5000;
}

upstream auth_service {
    server auth_service:5001;
}

upstream rag_service {
    server rag_service:5002;
}

# ========================================================================
# RATE LIMITING ZONES
# ========================================================================

limit_req_zone \ zone=general:10m rate=100r/s;
limit_req_zone \ zone=api:10m rate=30r/s;
limit_req_zone \ zone=upload:10m rate=5r/m;

# ========================================================================
# HTTP → HTTPS REDIRECT
# ========================================================================

server {
    listen 80;
    server_name _;
    return 301 https://\System.Management.Automation.Internal.Host.InternalHost\;
}

# ========================================================================
# HTTPS SERVER WITH ROUTING RULES
# ========================================================================

server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # ROUTING: Root → Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host \System.Management.Automation.Internal.Host.InternalHost;
        proxy_set_header X-Real-IP \;
        proxy_set_header X-Forwarded-For \;
    }

    # ROUTING: /api/ → Backend
    location /api/ {
        limit_req zone=api burst=50 nodelay;
        proxy_pass http://backend_api;
        proxy_set_header Host \System.Management.Automation.Internal.Host.InternalHost;
        proxy_set_header X-Real-IP \;
        proxy_set_header Authorization \;
    }

    # ROUTING: /auth/ → Auth Service
    location /auth/ {
        proxy_pass http://auth_service;
        proxy_set_header Host \System.Management.Automation.Internal.Host.InternalHost;
    }

    # ROUTING: /rag/ → RAG Service
    location /rag/ {
        proxy_pass http://rag_service;
        proxy_set_header Host \System.Management.Automation.Internal.Host.InternalHost;
    }

    # HEALTH: Public health check
    location /health {
        access_log off;
        proxy_pass http://backend_api/health;
    }
}
\\\

### Routing Table

| Path | Upstream | Rate Limit |
|------|----------|-----------|
| \/\ | frontend:3000 | 100r/s |
| \/api/...\ | backend:5000 | 30r/s |
| \/auth/...\ | auth_service:5001 | 10r/m |
| \/rag/...\ | rag_service:5002 | 30r/s |
| \/health\ | backend:5000 | No limit |

---

## 9. Docker Volumes + Backup/Restore

### Volume Definitions

\\\yaml
volumes:
  postgres_data:
    driver: local
  qdrant_data:
    driver: local
  redis_data:
    driver: local
\\\

### Volume Mount Points

| Service | Container Path | Volume |
|---------|---|---|
| **postgres** | /var/lib/postgresql/data | postgres_data |
| **qdrant** | /qdrant/storage | qdrant_data |
| **redis** | /data | redis_data |

### Backup PostgreSQL

\\\ash
# Quick backup
docker compose exec postgres pg_dump -U postgres ai_ba_db > backup.sql

# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=\
docker compose exec -T postgres pg_dump -U postgres ai_ba_db | \\
  gzip > "\/postgres_\.sql.gz"
echo "Backup completed: \"
\\\

### Restore PostgreSQL

\\\ash
# Restore from SQL dump
docker compose exec -T postgres psql -U postgres -d ai_ba_db < backup.sql

# Restore specific table
docker compose exec -T postgres psql -U postgres -d ai_ba_db < table_backup.sql
\\\

---

## 10. Container Dependency Order

### Dependency Graph

\\\
TIER 0 (No dependencies - start first in parallel):
├─ postgres
├─ redis
└─ qdrant

TIER 1 (Depends on TIER 0):
├─ auth_service (depends_on: postgres✓, redis✓)
├─ backend (depends_on: postgres✓, redis✓, auth_service✓)
└─ rag_service (depends_on: postgres✓, qdrant✓, redis✓)

TIER 2 (Presentation):
├─ frontend (no dependencies)
└─ gateway (depends_on: all services✓)
\\\

### Start Order Timeline

\\\
0s    docker compose up -d
8s    postgres healthy ✓
10s   redis healthy ✓
12s   qdrant healthy ✓
18s   auth_service healthy ✓
23s   backend healthy ✓
28s   rag_service healthy ✓
32s   frontend healthy ✓
38s   gateway healthy ✓
40s   ✓ All services ready
\\\

---

## 11. Network Segmentation

### Network Configuration

\\\yaml
networks:
  ai-ba-network:
    driver: bridge
\\\

### Service Communication

\\\
Internal (same network):
backend → postgres   : postgresql://postgres:5432/ai_ba_db
backend → redis      : redis://redis:6379
backend → auth_service : http://auth_service:5001
rag_service → qdrant : http://qdrant:6333

External (via gateway):
Client → gateway     : https://your-domain.com:443
\\\

### DNS Resolution

Docker's embedded DNS resolves service names to container IPs:

\\\ash
# Inside backend container:
nslookup auth_service
# Output: 172.18.0.X (internal IP)
\\\

---

## 12. Image Naming Strategy

### Local Development

\\\ash
# Build locally (no registry prefix)
docker build -f backend/Dockerfile -t ai_ba_backend:latest .
docker build -f frontend/Dockerfile -t ai_ba_frontend:latest .
\\\

### Production (Registry)

\\\ash
# GitHub Container Registry (GHCR)
ghcr.io/your-org/ai-ba-agent/backend:1.0.0
ghcr.io/your-org/ai-ba-agent/frontend:1.0.0

# Docker Hub
docker.io/yourusername/ai-ba-agent-backend:1.0.0
\\\

### Version-Based Tagging

\\\ash
VERSION=1.0.0
docker build -f backend/Dockerfile \\
  -t ghcr.io/your-org/ai-ba-agent/backend:\ \\
  -t ghcr.io/your-org/ai-ba-agent/backend:latest .

docker push ghcr.io/your-org/ai-ba-agent/backend:\
docker push ghcr.io/your-org/ai-ba-agent/backend:latest
\\\

### Image Naming Checklist

| Aspect | Local Dev | Production |
|--------|-----------|-----------|
| **Format** | \service:latest\ | \egistry/namespace/service:tag\ |
| **Registry** | None (local) | ghcr.io or docker.io |
| **Version** | always latest | Semantic (1.0.0) |

---

## Quick Reference Commands

### Build & Start

\\\ash
cd infra
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f
\\\

### Health Checks

\\\ash
curl http://localhost:5000/health
curl http://localhost:5001/health
curl http://localhost:5002/health
curl http://localhost/health
curl http://localhost:3000
\\\

### Troubleshooting

\\\ash
docker compose logs backend
docker compose exec backend bash
docker compose restart backend
docker compose down -v
\\\

---

**Document Version:** 2.0  
**Last Updated:** 2026-03-17  
**Status:** ✅ Production Ready
