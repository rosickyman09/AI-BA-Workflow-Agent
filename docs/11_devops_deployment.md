# DevOps & Deployment Guide
**Version:** 1.0  
**Date:** 2026-03-15  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Phase:** MVP Phase 1

---

## 1. Architecture Overview

### 1.1 Deployment Architecture

```
┌────────────────────────────────────────────────────┐
│       Internet / Users                             │
└────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────┐
│  Nginx Gateway (Port 80/443)                       │
│  - TLS Termination                                 │
│  - Load Balancing                                  │
│  - Rate Limiting                                   │
└────────────────────────────────────────────────────┘
         ↓                    ↓                    ↓
┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐
│  Frontend       │  │  Backend API     │  │  RAG Service │
│  (Next.js)      │  │  (FastAPI)       │  │  (Python)    │
│  Port 3000      │  │  Port 8000       │  │  Port 8001   │
└─────────────────┘  └──────────────────┘  └──────────────┘
                             ↓
                    ┌──────────────────────┐
                    │  PostgreSQL (Port 5432) │
                    │  Data Storage          │
                    └──────────────────────┘
         ↙              │              ↘
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  Redis   │  │ Qdrant   │  │  S3/NAS  │
    │ Caching  │  │ Vectors  │  │Documents │
    └──────────┘  └──────────┘  └──────────┘
```

### 1.2 Service Ports

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Nginx (Gateway) | 80 | HTTP | Redirect to HTTPS |
| Nginx (Gateway) | 443 | HTTPS | Production traffic |
| Frontend | 3000 | HTTP | Development only |
| Backend API | 8000 | HTTP | Internal only |
| RAG Service | 8001 | HTTP | Internal only |
| PostgreSQL | 5432 | TCP | Internal only |
| Redis | 6379 | TCP | Internal only |
| Qdrant | 6333 | HTTP | Internal only |

---

## 2. Docker & Container Setup

### 2.1 Docker Compose Configuration

**File:** `docker-compose.yml`

```yaml
version: '3.9'

services:
  # ==================== Nginx Gateway ====================
  nginx:
    image: nginx:1.25-alpine
    container_name: ai_ba_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./gateway/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./gateway/certs:/etc/nginx/certs:ro
      - ./gateway/conf.d:/etc/nginx/conf.d:ro
    networks:
      - ai_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      - frontend
      - backend
      - rag_service

  # ==================== Frontend ====================
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: ai_ba_frontend
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=http://localhost/api
    networks:
      - ai_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      - backend

  # ==================== Backend API ====================
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ai_ba_backend
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - DATABASE_URL=postgresql://user:password@postgres:5432/ai_ba_agent
      - REDIS_URL=redis://redis:6379/0
      - QDRANT_URL=http://qdrant:6333
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    volumes:
      - /data/uploads:/app/uploads
      - /data/logs:/app/logs
    networks:
      - ai_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy

  # ==================== RAG Service ====================
  rag_service:
    build:
      context: ./rag_service
      dockerfile: Dockerfile
    container_name: ai_ba_rag
    ports:
      - "8001:8001"
    environment:
      - APP_ENV=production
      - DATABASE_URL=postgresql://user:password@postgres:5432/ai_ba_agent
      - QDRANT_URL=http://qdrant:6333
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - /data/logs:/app/logs
    networks:
      - ai_network
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy

  # ==================== PostgreSQL ====================
  postgres:
    image: postgres:15-alpine
    container_name: ai_ba_postgres
    environment:
      POSTGRES_USER: ${DB_USER:-user}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-secure_password}
      POSTGRES_DB: ai_ba_agent
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/migrations:/docker-entrypoint-initdb.d
    networks:
      - ai_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-user}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ==================== Redis ====================
  redis:
    image: redis:7-alpine
    container_name: ai_ba_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - ai_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    command: redis-server --appendonly yes

  # ==================== Qdrant Vector DB ====================
  qdrant:
    image: qdrant/qdrant:v1.7
    container_name: ai_ba_qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT_API_KEY=${QDRANT_API_KEY}
    networks:
      - ai_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3

# ==================== Volumes ====================
volumes:
  postgres_data:
  redis_data:
  qdrant_data:

# ==================== Networks ====================
networks:
  ai_network:
    driver: bridge
```

### 2.2 Environment Variables

**File:** `.env.production`

```bash
# Environment
APP_ENV=production
NODE_ENV=production

# Database
DB_USER=ai_user
DB_PASSWORD=secure_db_password_change_me
DB_HOST=postgres
DB_PORT=5432
DB_NAME=ai_ba_agent

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=secure_redis_password_change_me

# Qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=secure_qdrant_key_change_me

# API Keys (Load from Secrets Manager in production!)
OPENAI_API_KEY=${OPENAI_API_KEY}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

# Frontend
NEXT_PUBLIC_API_URL=https://api.example.com
NEXT_PUBLIC_APP_NAME=AI Business Assistant

# Backend
API_PORT=8000
RAG_SERVICE_URL=http://rag_service:8001
JWT_SECRET_KEY=super_secret_jwt_key_change_me
JWT_ALGORITHM=HS256
TOKEN_EXPIRY_HOURS=1

# Features
ENABLE_RAG=true
ENABLE_AGENTS=true
ENABLE_WEBHOOKS=false

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 3. Dockerfile Configurations

### 3.1 Backend Dockerfile

**File:** `backend/Dockerfile`

```dockerfile
# Multi-stage build for optimization
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 Frontend Dockerfile

**File:** `frontend/Dockerfile`

```dockerfile
# Build stage
FROM node:20-alpine as builder

WORKDIR /app

# Copy files
COPY package*.json ./
RUN npm ci

COPY . .

# Build application
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1000 appuser && adduser -D -u 1000 -G appuser appuser

# Copy built application
COPY --from=builder --chown=appuser:appuser /app/.next ./.next
COPY --from=builder --chown=appuser:appuser /app/public ./public
COPY --chown=appuser:appuser package*.json ./

# Install production dependencies only
RUN npm ci --only=production

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

# Run application
CMD ["npm", "start"]
```

### 3.3 RAG Service Dockerfile

**File:** `rag_service/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## 4. Nginx Configuration

**File:** `gateway/nginx.conf`

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;

    # Upstream configuration
    upstream frontend {
        server frontend:3000;
        keepalive 32;
    }

    upstream backend {
        server backend:8000;
        keepalive 32;
    }

    upstream rag_service {
        server rag_service:8001;
        keepalive 32;
    }

    # HTTP to HTTPS redirect
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name api.example.com;

        # SSL certificates
        ssl_certificate /etc/nginx/certs/cert.pem;
        ssl_certificate_key /etc/nginx/certs/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }

        # Frontend routes
        location / {
            limit_req zone=general burst=50 nodelay;
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
        }

        # API routes
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # RAG Service routes
        location /rag/ {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://rag_service/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        # Static assets caching
        location ~* ^/(_next|public)/ {
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

---

## 5. Deployment Steps

### 5.1 Local Development

```bash
# Clone repository
git clone <repo> && cd ai-ba-agent

# Create .env.development
cp .env.example .env.development
# Edit .env.development with your local values

# Start services
docker-compose -f docker-compose.dev.yml up -d

# Check health
docker-compose logs -f

# Access
# Frontend: http://localhost:3000
# API: http://localhost:8000/docs
# RAG: http://localhost:8001/docs
```

### 5.2 Staging/Production Deployment

```bash
# 1. Prepare environment
export ENVIRONMENT=production

# 2. Build images (if not using registry)
docker-compose build

# 3. Start services
docker-compose -f docker-compose.yml up -d

# 4. Run database migrations
docker-compose exec backend alembic upgrade head

# 5. Verify health
docker-compose exec nginx curl http://localhost/health

# 6. Check logs
docker-compose logs -f

# 7. Monitoring dashboard
# Open: http://localhost:9090 (if Prometheus enabled)
```

---

## 6. Health Checks & Monitoring

### 6.1 Health Check Endpoints

| Service | Endpoint | Method |
|---------|----------|--------|
| Nginx | `/health` | GET (200 OK) |
| Backend | `/health` | GET (200 OK) |
| RAG Service | `/health` | GET (200 OK) |
| PostgreSQL | Port 5432 | TCP connection |
| Redis | `PING` | RESP protocol |
| Qdrant | `/health` | GET (200 OK) |

### 6.2 Health Check Script

**File:** `infra/health_check.sh`

```bash
#!/bin/bash

echo "=== Health Check Report ==="

# Check Nginx
echo -n "Nginx: "
curl -s http://localhost/health > /dev/null && echo "✓ OK" || echo "✗ FAILED"

# Check Backend
echo -n "Backend API: "
curl -s http://localhost:8000/health > /dev/null && echo "✓ OK" || echo "✗ FAILED"

# Check RAG Service
echo -n "RAG Service: "
curl -s http://localhost:8001/health > /dev/null && echo "✓ OK" || echo "✗ FAILED"

# Check PostgreSQL
echo -n "PostgreSQL: "
docker-compose exec -T postgres pg_isready > /dev/null 2>&1 && echo "✓ OK" || echo "✗ FAILED"

# Check Redis
echo -n "Redis: "
docker-compose exec -T redis redis-cli ping > /dev/null 2>&1 && echo "✓ OK" || echo "✗ FAILED"

# Check Qdrant
echo -n "Qdrant: "
curl -s http://localhost:6333/health > /dev/null && echo "✓ OK" || echo "✗ FAILED"

echo "===================="
```

### 6.3 Running Health Checks

```bash
chmod +x infra/health_check.sh
./infra/health_check.sh
```

---

## 7. Logging & Log Management

### 7.1 Log Aggregation

**File:** `docker-compose.yml` (Add logging section)

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "service=backend"
```

### 7.2 View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend

# Timestamp added
docker-compose logs -f -t backend
```

---

## 8. Scaling & Performance

### 8.1 Increase Backend Instances (Docker Swarm)

```bash
docker service scale backend=3
```

### 8.2 Database Connection Pooling

Set in `backend/config.py`:
```python
DATABASE_POOL_SIZE = 20
DATABASE_POOL_RECYCLE = 3600
```

### 8.3 Redis Caching Strategy

```python
# Cache queries for 1 hour
cache.set(f"query:{query_id}", result, ttl=3600)

# Cache documents for 24 hours
cache.set(f"doc:{doc_id}", content, ttl=86400)
```

---

## 9. Backup & Disaster Recovery

### 9.1 Database Backup

```bash
# Manual backup
docker-compose exec postgres pg_dump -U user ai_ba_agent | gzip > backup_$(date +%Y%m%d).sql.gz

# Automated backup (cron job)
0 2 * * * docker-compose exec postgres pg_dump -U user ai_ba_agent | gzip > /backups/backup_$(date +%Y%m%d).sql.gz
```

### 9.2 Restore from Backup

```bash
gunzip < backup_20260315.sql.gz | docker-compose exec -T postgres psql -U user ai_ba_agent
```

### 9.3 Volume Backups

```bash
# Backup volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data.tar.gz -C /data .

# Restore volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_data.tar.gz -C /data
```

---

## 10. Troubleshooting

### 10.1 Service Not Starting

```bash
# Check logs
docker-compose logs <service_name>

# Inspect service
docker-compose ps

# Check configuration
docker-compose config

# Rebuild image
docker-compose build --no-cache <service_name>
```

### 10.2 Database Connection Errors

```bash
# Check PostgreSQL is running
docker-compose exec postgres psql -U user -d ai_ba_agent -c "SELECT 1"

# Check connection string
echo $DATABASE_URL

# Restart service
docker-compose restart backend
```

### 10.3 Memory Issues

```bash
# Check memory usage
docker stats

# Increase limits in docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

---

## 11. Security Checklist

- [ ] Change all default passwords in `.env`
- [ ] Generate strong JWT secret key
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Use environment-specific .env files
- [ ] Never commit `.env` files to Git
- [ ] Enable SQL injection protection
- [ ] Configure firewall rules
- [ ] Set up rate limiting
- [ ] Enable CORS only for trusted origins
- [ ] Encrypt sensitive data in database
- [ ] Regular security patches
- [ ] Monitor access logs for suspicious activity

---

## END OF DEVOPS & DEPLOYMENT GUIDE
