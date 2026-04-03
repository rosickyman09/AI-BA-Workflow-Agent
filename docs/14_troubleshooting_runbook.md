# Troubleshooting Guide & Runbook
**Version:** 1.0  
**Date:** 2026-03-15  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Phase:** MVP Phase 1

---

## 1. Quick Diagnostic Checklist

When something breaks, start here:

```
□ Check system health: ./infra/health_check.sh
□ Check container status: docker-compose ps
□ Review recent logs: docker-compose logs --tail=100
□ Verify network connectivity: docker exec ai_ba_backend ping redis
□ Test database: docker-compose exec postgres psql -U user ai_ba_agent -c "SELECT 1"
□ Validate configuration: env | grep -i database_url
□ Check disk space: df -h
□ Monitor CPU/Memory: docker stats
```

---

## 2. Common Issues & Solutions

### 2.1 Service Startup Issues

#### Problem: Container exits immediately

**Symptoms:**
```
ai_ba_backend exited with code 1
```

**Diagnosis:**
```bash
docker-compose logs backend | tail -50
```

**Common Causes & Solutions:**

1. **Database Connection Failure**
   ```
   Error: could not connect to server: Connection refused
   ```
   - Check PostgreSQL is running: `docker-compose ps postgres`
   - Verify connection string: `echo $DATABASE_URL`
   - Wait for PostgreSQL readiness: `docker-compose up postgres -d && sleep 10`

2. **Environment Variables Not Set**
   ```
   Error: KeyError: 'DATABASE_URL'
   ```
   - Solution: Create `.env` file with required variables
   - Reference: `.env.example`
   - Reload: `source .env && docker-compose up -d backend`

3. **Port Already in Use**
   ```
   Error: bind: address already in use
   ```
   - Find process: `lsof -i :8000`
   - Kill process: `kill -9 PID`
   - Or change port in docker-compose.yml

4. **Memory Insufficient**
   ```
   Error: Cannot allocate memory
   ```
   - Increase Docker memory: Docker Desktop settings → Resources
   - Minimum: 4GB, Recommended: 8GB

---

#### Problem: Service crashes after starting

**Symptoms:**
```
ai_ba_backend is not running
```

**Solution 1: Check for runtime errors**
```bash
docker-compose logs backend -f --tail=100
```

**Solution 2: Restart with verbose output**
```bash
docker-compose up backend
# Don't use -d flag to see output
```

**Solution 3: Increase startup time**
```yaml
healthcheck:
  start_period: 30s  # Increase from default
```

---

### 2.2 Database Issues

#### Problem: PostgreSQL won't connect

**Error:**
```
psycopg2.OperationalError: could not connect to server: 
Connection refused. Is the server running?
```

**Solutions:**

1. **Check PostgreSQL is running:**
```bash
docker-compose ps postgres
# Status should be "Up"
```

2. **Verify network connectivity:**
```bash
docker-compose exec backend ping postgres
# Should receive PONG
```

3. **Check credentials:**
```bash
docker-compose exec postgres psql -U user -d ai_ba_agent -c "SELECT 1"
# Should return: 1
```

4. **Restart PostgreSQL:**
```bash
docker-compose restart postgres
# Wait 10 seconds for startup
sleep 10
docker-compose logs postgres | grep "ready to accept"
```

---

#### Problem: Database is locked

**Error:**
```
database is locked
```

**Solution:**

1. **Identify blocking query:**
```sql
SELECT pid, usename, state FROM pg_stat_activity 
WHERE datname = 'ai_ba_agent' AND state != 'idle';
```

2. **Kill blocking connection:**
```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE datname = 'ai_ba_agent' AND usename != 'current_user';
```

3. **Last resort - restart:**
```bash
docker-compose restart postgres
```

---

#### Problem: Out of disk space

**Error:**
```
ERROR: could not write block 12345 of relation base/16387/12345: No space left on device
```

**Solution:**

1. **Check disk usage:**
```bash
docker system df
df -h
```

2. **Clean Docker:**
```bash
docker system prune -a
# Remove unused images and containers

docker volume prune
# Remove unused volumes (⚠️ WARNING - may delete data)
```

3. **Backup and restore data:**
```bash
# Backup
docker-compose exec postgres pg_dump ai_ba_agent | gzip > backup.sql.gz

# Remove volume
docker-compose down -v

# Free space
df -h

# Restore
gunzip < backup.sql.gz | docker-compose exec -T postgres psql ai_ba_agent
```

---

### 2.3 Network & Connectivity Issues

#### Problem: Cannot reach backend from frontend

**Symptoms:**
```
Error: Failed to fetch http://localhost:8000/api/v1/...
ERR_NAME_NOT_RESOLVED
```

**Solutions:**

1. **Check Nginx is routing correctly:**
```bash
curl -v http://localhost/api/v1/docs
# Should return API docs
```

2. **Test backend directly:**
```bash
docker-compose exec frontend curl http://backend:8000/health
# Should return 200
```

3. **Check Docker network:**
```bash
docker network ls
docker inspect ai_ba_agent_ai_network
```

4. **Fix Nginx routing:**
```nginx
location /api/ {
    proxy_pass http://backend:8000/;
    proxy_set_header Host $host;
}
```

---

#### Problem: CORS errors

**Error:**
```
Access to XMLHttpRequest blocked by CORS policy
```

**Solution:**

1. **Check CORS headers:**
```bash
curl -I -H "Origin: http://localhost:3000" http://localhost/api/v1/docs
```

2. **Configure FastAPI CORS:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### 2.4 Authentication Issues

#### Problem: Invalid token error

**Error:**
```
{"detail": "Invalid authentication credentials"}
```

**Causes & Solutions:**

1. **Token expired:**
   - Refresh token: `POST /api/v1/auth/refresh`
   - Or login again

2. **Token format incorrect:**
   ```
   ✓ Correct:  Authorization: Bearer eyJhbGc...
   ✗ Wrong:    Authorization: eyJhbGc...
   ```

3. **Wrong secret key:**
   - Verify `JWT_SECRET_KEY` in `.env`
   - Must be same across restarts

4. **Token from different environment:**
   - Dev token won't work in production
   - Generate new token for current environment

---

#### Problem: Cannot login

**Steps to debug:**

1. **Manually test login endpoint:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

2. **Check user exists:**
```bash
docker-compose exec postgres psql -U user ai_ba_agent -c \
  "SELECT id, email FROM users WHERE email = 'user@example.com';"
```

3. **Verify password hash:**
```bash
docker-compose exec backend python -c \
  "from src.services.auth import verify_password; \
   print(verify_password('password123', 'hash_from_db'))"
```

---

### 2.5 API & Response Issues

#### Problem: API timeout

**Error:**
```
504 Gateway Timeout
```

**Diagnosis & Solutions:**

1. **Check backend load:**
```bash
docker stats backend
# Monitor CPU and Memory
```

2. **Check slow queries:**
```bash
# In logs
docker-compose logs backend | grep "duration"
```

3. **Optimize database queries:**
```sql
-- Find slow queries
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
SELECT query, mean_exec_time FROM pg_stat_statements 
ORDER BY mean_exec_time DESC LIMIT 10;
```

4. **Increase timeout:**
```nginx
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;
```

---

#### Problem: 500 Internal Server Error

**Steps:**

1. **Get detailed error:**
```bash
docker-compose logs backend | tail -50
```

2. **Enable debug mode:**
```python
# In main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

3. **Test endpoint manually:**
```bash
curl -X POST http://localhost:8000/api/v1/queries/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"test"}'
```

---

### 2.6 Document Processing Issues

#### Problem: Document stuck in "processing" status

**Symptoms:**
```
Document status: "processing" for > 5 minutes
```

**Solution:**

1. **Check RAG service logs:**
```bash
docker-compose logs rag_service -f --tail=50
```

2. **Check task status:**
```bash
docker-compose exec backend python -c \
  "from src.database import db; \
   from src.models import Document; \
   doc = db.query(Document).filter_by(id='doc_id').first(); \
   print(doc.status, doc.error_message)"
```

3. **Reset document status:**
```bash
docker-compose exec postgres psql -U user ai_ba_agent -c \
  "UPDATE documents SET status='pending', error_message=NULL \
   WHERE id='doc_id';"
```

4. **Restart RAG service:**
```bash
docker-compose restart rag_service
```

---

#### Problem: Vector embeddings not created

**Symptoms:**
```
Document processed but embedding_status='pending'
```

**Solution:**

1. **Check Qdrant connection:**
```bash
curl http://localhost:6333/health
```

2. **Verify embedding model:**
```bash
docker-compose exec rag_service python -c \
  "from sentence_transformers import SentenceTransformer; \
   model = SentenceTransformer('all-MiniLM-L6-v2'); \
   print(model.encode('test'))"
```

3. **Manually trigger embedding:**
```bash
docker-compose exec rag_service python -c \
  "from src.services.embedding_service import embed_document; \
   embed_document('doc_id')"
```

---

### 2.7 Search & RAG Issues

#### Problem: Search returns no results

**Steps to debug:**

1. **Check documents exist:**
```bash
curl -X GET http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN"
```

2. **Check embeddings in Qdrant:**
```bash
curl http://localhost:6333/collections
```

3. **Test search manually:**
```bash
curl -X POST http://localhost:8000/api/v1/queries/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"test","top_k":5}'
```

4. **Verify chunks created:**
```bash
docker-compose exec postgres psql -U user ai_ba_agent -c \
  "SELECT COUNT(*) FROM document_chunks WHERE document_id='doc_id';"
```

---

#### Problem: RAG response quality is poor

**Solutions:**

1. **Adjust search parameters:**
```python
# Increase top_k to get more context
search(query, top_k=10)  # Instead of 5

# Check similarity threshold
# results = [r for r in results if r.similarity > 0.7]
```

2. **Optimize prompt:**
```python
# Better context window
SYSTEM_PROMPT = """You are a business analyst assistant. 
Use the provided documents to answer questions.
If you don't know, say 'I don't have that information'."""
```

3. **Use better model:**
```python
# Switch to GPT-4-turbo
model = "gpt-4-turbo"
# Higher cost but better quality
```

---

### 2.8 Memory & Performance Issues

#### Problem: High memory usage

**Symptoms:**
```
WARNING: Memory usage 85%+
```

**Solutions:**

1. **Identify memory leaks:**
```bash
docker stats --no-stream
# Look for growing memory
```

2. **Reduce batch size:**
```python
BATCH_SIZE = 10  # Reduce from 50
```

3. **Clear caches:**
```bash
docker-compose exec redis redis-cli FLUSHALL
```

4. **Restart services:**
```bash
docker-compose restart backend rag_service
```

---

#### Problem: Slow database queries

**Solution:**

1. **Find slow queries:**
```sql
SELECT query, mean_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC LIMIT 5;
```

2. **Add indexes:**
```sql
CREATE INDEX idx_documents_user_created 
ON documents(user_id, created_at DESC);

CREATE INDEX idx_chunks_document 
ON document_chunks(document_id);
```

3. **Analyze execution plan:**
```sql
EXPLAIN ANALYZE 
SELECT * FROM documents WHERE user_id = 'user_123';
```

---

### 2.9 Redis Issues

#### Problem: Redis connection refused

**Symptoms:**
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379.
```

**Solution:**

1. **Check Redis is running:**
```bash
docker-compose ps redis
```

2. **Test Redis connection:**
```bash
docker-compose exec redis redis-cli ping
```

3. **Restart Redis:**
```bash
docker-compose restart redis
```

4. **Check Redis logs:**
```bash
docker-compose logs redis
```

---

#### Problem: Redis memory full

**Solution:**

1. **Check memory usage:**
```bash
docker-compose exec redis redis-cli INFO memory
```

2. **Clear old data:**
```bash
docker-compose exec redis redis-cli FLUSHDB
# Warning: Clears cache, performance may degrade
```

3. **Set eviction policy:**
```bash
docker-compose exec redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

### 2.10 Qdrant Issues

#### Problem: Qdrant collection not found

**Error:**
```
CollectionNotFound: Collection 'documents' does not exist
```

**Solution:**

1. **Create collection:**
```bash
curl -X PUT http://localhost:6333/collections/documents \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    }
  }'
```

2. **Verify collection exists:**
```bash
curl http://localhost:6333/collections/documents
```

---

#### Problem: Slow vector search

**Solution:**

1. **Check index status:**
```bash
curl http://localhost:6333/collections/documents
```

2. **Enable HNSW index:**
```bash
curl -X PATCH http://localhost:6333/collections/documents \
  -H "Content-Type: application/json" \
  -d '{
    "hnsw_config": {
      "m": 16,
      "ef_construct": 200,
      "full_scan_threshold": 10000
    }
  }'
```

---

## 3. Monitoring & Alerting

### 3.1 Key Metrics to Monitor

```bash
# System Health
- CPU Usage: < 80%
- Memory Usage: < 85%
- Disk Usage: < 90%

# Application Health
- Error Rate: < 0.5%
- Response Time (p95): < 2000ms
- Uptime: > 99%

# Database Health
- Connection Pool: < 90% full
- Slow Queries: < 5/minute
- Replication Lag: < 1 second

# Vector DB Health
- Qdrant Response Time: < 500ms
- Vector Search Accuracy: > 0.85
```

### 3.2 Health Check Script

**File:** `infra/comprehensive_health_check.sh`

```bash
#!/bin/bash

echo "=== Comprehensive Health Check ==="
echo "Time: $(date)"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

check_service() {
    local service=$1
    local endpoint=$2
    local expected=$3 || 200
    
    status=$(curl -s -o /dev/null -w "%{http_code}" $endpoint)
    if [ "$status" == "$expected" ]; then
        echo -e "${GREEN}✓ $service${NC}"
        return 0
    else
        echo -e "${RED}✗ $service (Status: $status)${NC}"
        return 1
    fi
}

# Check services
check_service "Nginx" "http://localhost/health" 200
check_service "Backend API" "http://localhost:8000/health" 200
check_service "RAG Service" "http://localhost:8001/health" 200
check_service "Qdrant" "http://localhost:6333/health" 200

# Check databases
echo ""
echo "Checking databases..."

docker-compose exec -T postgres pg_isready > /dev/null && \
    echo -e "${GREEN}✓ PostgreSQL${NC}" || \
    echo -e "${RED}✗ PostgreSQL${NC}"

docker-compose exec -T redis redis-cli ping > /dev/null 2>&1 && \
    echo -e "${GREEN}✓ Redis${NC}" || \
    echo -e "${RED}✗ Redis${NC}"

echo ""
echo "=== Check Complete ==="
```

---

## 4. Recovery Procedures

### 4.1 Complete System Recovery

```bash
#!/bin/bash

echo "Starting complete system recovery..."

# Step 1: Stop all services
echo "1. Stopping services..."
docker-compose down

# Step 2: Clear caches
echo "2. Clearing caches..."
docker system prune -f

# Step 3: Restart services
echo "3. Restarting services..."
docker-compose up -d

# Step 4: Wait for startup
echo "4. Waiting for services to start..."
sleep 15

# Step 5: Run health checks
echo "5. Running health checks..."
./infra/health_check.sh

echo "Recovery complete!"
```

### 4.2 Database Recovery from Backup

```bash
#!/bin/bash

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: recover_db.sh <backup_file>"
    exit 1
fi

echo "Recovering database from $BACKUP_FILE..."

# Step 1: Stop backend
docker-compose stop backend rag_service

# Step 2: Restore database
gunzip < $BACKUP_FILE | \
    docker-compose exec -T postgres psql -U user ai_ba_agent

# Step 3: Verify
docker-compose exec postgres psql -U user ai_ba_agent -c "SELECT COUNT(*) FROM users;"

# Step 4: Restart services
docker-compose up -d backend rag_service

echo "Database recovery complete!"
```

---

## 5. Performance Tuning

### 5.1 Database Optimization

```sql
-- Rebuild indexes
REINDEX DATABASE ai_ba_agent;

-- Vacuum and analyze
VACUUM ANALYZE;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes 
ORDER BY idx_scan DESC;

-- Remove unused indexes
DROP INDEX CONCURRENTLY idx_unused;
```

### 5.2 Application Optimization

```python
# Implement caching
@cache.cached(timeout=3600)  # Cache for 1 hour
def get_popular_documents():
    return db.query(Document).filter(...).all()

# Use connection pooling
from sqlalchemy.pool import QueuePool
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40
)

# Batch operations
for chunk in chunks_generator(documents, batch_size=100):
    db.bulk_insert_mappings(DocumentChunk, chunk)
    db.commit()
```

---

## 6. Emergency Contacts

```
🚨 CRITICAL (System Down):
   - DevOps Lead: +1 (555) 123-4567
   - On-Call Engineer: [PagerDuty]

⚠️  HIGH (Major Feature Broken):
   - Backend Lead: +1 (555) 234-5678
   - RAG Lead: +1 (555) 345-6789

ℹ️  MEDIUM (Performance Degradation):
   - Database Admin: +1 (555) 456-7890
   - DevOps Team: team@example.com

📧 Email: support@example.com
💬 Slack: #incidents
```

---

## 7. Escalation Procedure

```
Level 1: Automated Alerts (0-5 min)
  ├─ Check health endpoints
  ├─ Review recent logs
  └─ Try basic restart

Level 2: On-Call Engineer (5-15 min)
  ├─ Comprehensive diagnostics
  ├─ Apply targeted fixes
  └─ Escalate if needed

Level 3: Team Lead (15-30 min)
  ├─ Deep investigation
  ├─ Architecture review
  └─ Consider rollback

Level 4: Engineering Manager (30+ min)
  ├─ Business impact assessment
  ├─ Communication to stakeholders
  └─ Post-incident review
```

---

## END OF TROUBLESHOOTING GUIDE
