# Startup Documentation - AI BA Agent

**Version:** 2.0  
**Date:** 2026-03-17  
**Status:** Production Ready  

---

## Quick Start

### Prerequisites

- Docker (20.10+)
- Docker Compose (2.0+)
- At least 4GB RAM available
- Ports 80, 443, 5000, 5001, 5002, 3000, 5432, 6333, 6379 available

### Start All Services

```bash
cd infra/scripts
chmod +x start.sh stop.sh
./start.sh
```

The script will:
1. Build all Docker images
2. Start infrastructure (postgres, redis, qdrant)
3. Wait for infrastructure to be healthy
4. Start application services (auth, backend, rag)
5. Start presentation layer (frontend, gateway)
6. Verify all services are healthy

Expected startup time: 40-60 seconds

### Access Applications

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:5000
- **Auth Service:** http://localhost:5001
- **RAG Service:** http://localhost:5002
- **Database:** localhost:5432
- **Redis Cache:** localhost:6379
- **Vector DB:** http://localhost:6333

---

## Detailed Startup Process

### Step 1: Building Docker Images

```bash
docker-compose build
```

Only needed on first run or after code changes. The build process:
- Caches dependencies in multi-stage builds
- Minimizes final image sizes
- Validates Dockerfiles and configurations

**Expected output:**
```
Building postgres      ... skipped (uses base image)
Building redis         ... skipped (uses base image)
Building qdrant        ... skipped (uses base image)
Building auth_service  ... done
Building backend       ... done
Building rag_service   ... done
Building frontend      ... done
Building gateway       ... done
```

### Step 2: Starting Infrastructure

```bash
docker-compose up -d postgres redis qdrant
```

Starts the core data services:
- **postgres:15-alpine** - Application database
- **redis:7-alpine** - Session cache and real-time data
- **qdrant:1.7.0** - Vector database for embeddings

These must be healthy before application services start.

**Health check verification:**
```bash
docker-compose ps postgres redis qdrant
# All should show "Up (healthy)"

# Test individually:
docker-compose exec postgres pg_isready
# Output: "accepting connections"
```

### Step 3: Starting Application Services

```bash
docker-compose up -d auth_service backend rag_service
```

Starts the API services:
- **auth_service:5001** - Authentication and JWT validation
- **backend:5000** - Main API and business logic
- **rag_service:5002** - RAG agent and LLM integration

These depend on infrastructure being healthy and start in parallel.

**Health check verification:**
```bash
curl http://localhost:5001/health
curl http://localhost:5000/health
curl http://localhost:5002/health

# All should return: {"status": "healthy", "service": "..."}
```

### Step 4: Starting Frontend and Gateway

```bash
docker-compose up -d frontend gateway
```

Starts presentation layer:
- **frontend:3000** - Next.js React application
- **gateway:80/443** - Nginx reverse proxy

The gateway depends on all other services being healthy to start.

**Health check verification:**
```bash
curl http://localhost:3000
# Should return HTML of login page

curl http://localhost:80/health
# Should return gateway health status
```

### Step 5: Verify Startup Completion

```bash
docker-compose ps
# All containers should show: "Up (healthy)"

docker-compose logs --tail=20
# Should show service initialization logs
```

---

## Health Check Details

### Each service includes automated health checks:

| Service | Check | Interval | Timeout | Retries |
|---------|-------|----------|---------|---------|
| postgres | pg_isready | 10s | 5s | 5 |
| redis | redis-cli ping | 10s | 5s | 5 |
| qdrant | echo OK | 30s | 10s | 3 |
| auth_service | GET /health | 15s | 10s | 3 |
| backend | GET /health | 15s | 10s | 3 |
| rag_service | GET /health | 15s | 10s | 3 |
| frontend | wget localhost:3000 | 15s | 10s | 3 |
| gateway | wget localhost/health | 15s | 10s | 3 |

### What "unhealthy" means:

- **Starting (0/5)**: Service has not yet passed any health checks
- **Healthy ✓**: Service passed health check and is ready
- **Unhealthy ✗**: Service failed health check repeatedly

### Troubleshooting unhealthy services:

```bash
# 1. View logs
docker-compose logs service_name

# 2. Check if port is listening
docker-compose exec service_name netstat -tlnp

# 3. Test endpoint manually
docker-compose exec service_name curl http://localhost:5000/health

# 4. Restart individual service
docker-compose restart service_name

# 5. Force rebuild and restart
docker-compose up -d --build service_name
```

---

## Environment Configuration

### Configuration files:

**Development (.env in infra/):**
```bash
DB_PASSWORD=postgres                    # WEAK OK for dev
JWT_SECRET=dev-secret-key-12345        # WEAK OK for dev
SERVICE_ENV=development
DEBUG=true
```

**Production (Railway/Cloud):**
```bash
DB_PASSWORD=<STRONG_32_CHAR_STRING>     # REQUIRED
JWT_SECRET=<STRONG_32_CHAR_STRING>      # REQUIRED
SERVICE_ENV=production
DEBUG=false
```

### Load configuration:

All services automatically load from `.env` file in infra/:

```bash
docker-compose up -d
# Reads: infra/.env for all environment variables
```

### Override specific variables:

```bash
# Run with custom database password
DB_PASSWORD=custom_password docker-compose up -d

# Or edit infra/.env and restart
nano infra/.env
docker-compose restart
```

---

## Docker Compose Structure

### Service Layers

```
GATEWAY LAYER (External Access)
  ├─ gateway:80/443 (Nginx reverse proxy)
  │   └─ Routes all traffic to services
  │
PRESENTATION LAYER (Web UI)
  ├─ frontend:3000 (Next.js React app)
  │   └─ Served by Nginx in production
  │
APPLICATION SERVICES LAYER (APIs)
  ├─ auth_service:5001 (JWT authentication)
  ├─ backend:5000 (Business logic)
  └─ rag_service:5002 (LLM agent)
  │   ├─ All depend on infrastructure ↓
  │
INFRASTRUCTURE LAYER (Data)
  ├─ postgres:5432 (Database)
  ├─ redis:6379 (Cache)
  └─ qdrant:6333 (Vector DB)
```

### Volume Persistence

```bash
# Volumes are stored in Docker's managed location:
# Linux/Mac: /var/lib/docker/volumes/
# Windows: \\wsl$\docker-desktop-data\mnt\wsl\docker-desktop

# List volumes:
docker volume ls | grep ai_ba

# Inspect volume details:
docker volume inspect ai_ba_postgres_data

# Backup volume data:
docker run --rm -v ai_ba_postgres_data:/data \
  -v $(pwd):/backup alpine tar czf /backup/backup.tar.gz -C /data .

# Restore from backup:
docker volume rm ai_ba_postgres_data
docker run --rm -v ai_ba_postgres_data:/data \
  -v $(pwd):/backup alpine tar xzf /backup/backup.tar.gz -C /data
```

---

## Stopping and Restarting

### Graceful Shutdown (preserves data)

```bash
cd infra/scripts
./stop.sh

# Or manually:
docker-compose down
```

### Restart All Services

```bash
docker-compose restart
```

### Restart Specific Service

```bash
docker-compose restart backend
```

### Complete Reset (deletes all data)

```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

---

## Monitoring and Logs

### View all logs:

```bash
docker-compose logs -f
# Follow logs from all services
# Press Ctrl+C to exit
```

### View specific service logs:

```bash
docker-compose logs -f backend
docker-compose logs -f gateway
docker-compose logs --tail=50 postgres
```

### Real-time container status:

```bash
watch -n 1 'docker-compose ps'
# Updates every second
```

### Health check history:

```bash
docker inspect ai_ba_backend --format='{{json .State.Health.Log}}'
# Shows last 3-5 health check results
```

---

## Common Issues and Solutions

### Issue: Port Already in Use

```bash
# Find what's using port 5000
sudo lsof -i :5000

# Kill process or change docker-compose mapping
# In docker-compose.yml:
# Change: - "5000:5000"
# To:     - "5001:5000" (external:internal)
```

### Issue: Docker Daemon Not Running

```bash
# Linux
sudo systemctl start docker

# macOS
open ~/Applications/Docker.app

# Windows
# Start Docker Desktop from Applications menu
```

### Issue: Out of Disk Space

```bash
# Clean up unused Docker image
docker system prune -a

# Remove specific volume
docker volume rm ai_ba_postgres_data

# Check disk usage
docker system df
```

### Issue: Database Connection Timeout

```bash
# Check if postgres is running
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres

# Force restart
docker-compose restart postgres

# Reset database (deletes data!)
docker-compose down -v
docker volume rm ai_ba_postgres_data
docker-compose up -d postgres
```

### Issue: Frontend Not Building

```bash
# Check Node.js version
docker-compose exec frontend node --version

# Rebuild frontend
docker-compose rebuild frontend

# View build logs
docker-compose logs frontend

# Full reset
docker-compose down
rm -rf frontend/.next frontend/node_modules
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

---

## Performance Tuning

### Increase Docker Resource Limits

Edit Docker Desktop settings:
- CPUs: Default is auto, set to your machine's core count
- Memory: Set to 50% of available RAM
- Disk: Ensure at least 20GB free space

### Optimize Database Performance

```bash
# Check postgres resources
docker-compose exec postgres \
  psql -U postgres -c "SHOW shared_buffers;"

# Monitor query performance
docker-compose exec postgres \
  psql -U postgres -c "SELECT * FROM pg_stat_statements LIMIT 10;"
```

### Cache and Optimize Frontend

```bash
# Clear Next.js build cache
docker-compose exec frontend rm -rf .next

# Rebuild with optimization
docker-compose exec frontend npm run build
```

---

## Production Deployment

### Before deploying to production:

1. ✓ Test locally with start.sh
2. ✓ Verify all health checks passing
3. ✓ Run full test suite (see run-*-tests.ps1)
4. ✓ Test realistic load (multiple concurrent users)
5. ✓ Configure strong database password
6. ✓ Set up SSL certificates
7. ✓ Configure production environment variables
8. ✓ Create database backups

### Deployment process:

```bash
# 1. SSH into production server
ssh user@production.server

# 2. Clone repository
git clone https://github.com/your-org/ai-ba-agent.git
cd ai-ba-agent

# 3. Create production .env file
cp infra/.env.prod infra/.env

# 4. Edit production secrets (don't use dev values!)
nano infra/.env

# 5. Build images
docker-compose build

# 6. Start services
cd infra/scripts
./start.sh

# 7. Verify startup
docker-compose ps
curl https://your-domain.com
```

---

## Rollback Procedure

### If deployment fails:

```bash
# 1. Stop current services
docker-compose down

# 2. Restore previous image
docker tag ai_ba_backend:old ai_ba_backend:latest

# 3. Restore database from backup (if applicable)
docker-compose exec -T postgres \
  psql -U postgres -d ai_ba_db < backup.sql

# 4. Restart with previous version
docker-compose up -d
```

---

## Reference

- [docs/05_deployment_plan.md](../05_deployment_plan.md) - Comprehensive deployment guide
- [infra/docker-compose.yml](../docker-compose.yml) - Service definitions
- [infra/.env.example](../.env.example) - Environment template
- [infra/healthchecks/healthcheck-config.yml](./healthchecks/healthcheck-config.yml) - Health check details

---

**Last Updated:** 2026-03-17  
**Status:** ✅ Production Ready
