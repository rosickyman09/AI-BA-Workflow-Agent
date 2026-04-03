# Quick Start Guide - Backend Services

## 🚀 5-Minute Setup

### Prerequisites
- Docker & Docker Compose installed
- Git repo cloned
- No services running on ports 80, 443, 5000-5002, 5432, 6333, 6379

### Step 1: Configure Environment
```bash
cd infra/
cp ../.env.example .env
```

Edit `.env` and add your API keys:
```
JWT_SECRET=your-secret-key-minimum-32-characters-long
DB_PASSWORD=your-postgres-password
OPENROUTER_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

### Step 2: Start Docker Compose
```bash
docker-compose up -d
```

Wait 30-60 seconds for all services to start and become healthy.

### Step 3: Verify Services
```bash
# Check service status
docker-compose ps

# Quick health checks
curl http://localhost/health
curl http://localhost:5000/health
curl http://localhost:5001/auth/health
curl http://localhost:5002/rag/health
```

All should return `"status": "healthy"`

### Step 4: Test APIs

**Login (Auth Service):**
```bash
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin123"
  }'
```

**Upload Document (Backend API):**
```bash
curl -X POST http://localhost/api/documents/upload \
  -F "file=@your_file.pdf"
```

**Search Knowledge Base (RAG Service):**
```bash
curl -X POST http://localhost/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-001",
    "query": "business requirements",
    "top_k": 5
  }'
```

## 📊 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Gateway (Public) | http://localhost | Nginx reverse proxy |
| Frontend | http://localhost:3000 | React UI |
| Backend API | http://localhost:5000 | Document orchestration |
| Auth Service | http://localhost:5001 | JWT authentication |
| RAG Service | http://localhost:5002 | AI agent orchestration |
| PostgreSQL | localhost:5432 | Relational database |
| Qdrant | http://localhost:6333 | Vector database |
| Redis | localhost:6379 | Cache |

## 🔍 API Documentation

Swagger/OpenAPI docs:
- Backend API: http://localhost:5000/docs
- Auth Service: http://localhost:5001/docs
- RAG Service: http://localhost:5002/docs

## 🛑 Stop Services

```bash
docker-compose down      # Stop all
docker-compose down -v   # Stop and remove volumes (reset database)
```

## 📝 Database Access

```bash
# Connect to PostgreSQL
docker exec -it ai_ba_postgres psql -U postgres -d ai_ba_db

# View tables
\dt

# Query example
SELECT * FROM users;
SELECT * FROM documents;
```

## 📋 Common Commands

```bash
# View logs
docker-compose logs -f                # All services
docker-compose logs -f backend        # Single service
docker-compose logs -f --tail=50      # Last 50 lines

# Rebuild images
docker-compose build

# Remove everything and start fresh
docker-compose down -v && docker-compose up -d

# SSH into container
docker exec -it ai_ba_backend bash
```

## ⚙️ Environment Variables

Key variables in `.env`:
- `JWT_SECRET` — JWT signing key (min 32 chars)
- `DB_PASSWORD` — PostgreSQL password
- `OPENROUTER_API_KEY` — LLM API access
- `ELEVENLABS_API_KEY` — Speech-to-text
- All others are optional for MVP

## ✅ Troubleshooting

**"Connection refused" on port 5000**
→ Check `docker-compose logs backend` for startup errors

**"postgres connection failed"**
→ Run `docker-compose down -v && docker-compose up -d` to reset

**"Health check failed"**
→ Wait another 30 seconds, containers may still be initializing

**"Port already in use"**
→ Run `lsof -i:5000` (macOS/Linux) or `netstat -ano | findstr 5000` (Windows)

## 🎯 Next Steps

1. ✅ Services are running
2. 📚 Review API docs at /docs endpoints
3. 🔧 Implement custom endpoints in `routers/`
4. 🧪 Write tests with pytest
5. 🚀 Deploy to Railway or your cloud platform

---

**Estimated setup time:** 5-10 minutes  
**All services healthy check:** Run `curl http://localhost/health` to verify everything is up
