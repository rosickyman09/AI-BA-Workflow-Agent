# QA Testing Execution Runbook

## Current Status

**Date:** 2026-03-17  
**System Status:** ⚠️ Docker Desktop Service Issue Detected  
**Testing Status:** ⏳ Ready to execute when Docker is fixed

---

## Issue: Docker Desktop Service Error

### Error Message
```
Docker Desktop is unable to start
terminating main distribution: un-mounting data disk: unmounting WSL VHDX
```

### Root Cause
WSL (Windows Subsystem for Linux) data disk unmount timeout. This is a known Docker Desktop issue on Windows systems.

### Quick Fix Steps

**Step 1: Stop Docker Services**
```powershell
# Close Docker Desktop application completely
# Check if any Docker processes remain and kill them
Get-Process | Where-Object { $_.ProcessName -like "*docker*" } | Stop-Process -Force
```

**Step 2: Reset Docker Disk**
```powershell
# In PowerShell (as Admin):
wsl --list --verbose
# Note which distro is used by Docker (usually "docker-desktop")

# Terminate the WSL distro
wsl --terminate docker-desktop

# Or terminate all WSL instances
wsl --shutdown
```

**Step 3: Restart Docker Desktop**
```powershell
# Restart Docker Desktop application
# Go to: C:\Program Files\Docker\Docker\Docker.exe
# Or use: docker version (which will auto-start the service)
```

**Step 4: Verify Docker is Running**
```powershell
docker ps
# Expected output: List of containers or empty list (no errors)

docker --version
# Expected output: Docker version XX.X.X
```

---

## Testing Workflow (Once Docker is Fixed)

### Phase 1: Start Infrastructure

```powershell
cd c:\Users\rosic\Documents\GitHub\AI-BA-Agent\infra

# Start only database services first (no builds needed)
docker-compose up -d postgres redis qdrant

# Wait for services to be healthy (check healthchecks pass)
docker-compose ps

# All three services should show "healthy" status
# Expected output:
#   ai_ba_postgres - Up (healthy)
#   ai_ba_redis    - Up (healthy)
#   ai_ba_qdrant   - Up (healthy)
```

### Phase 2: Run Module 1 Testing

```powershell
# Navigate to project root
cd c:\Users\rosic\Documents\GitHub\AI-BA-Agent

# Run Module 1 (Database) tests
.\run-module1-tests.ps1

# Expected output:
#   [TEST 1.1] Database Connectivity... ✓
#   [TEST 1.2] Schema Validation... ✓
#   [TEST 1.3] CRUD Operations... ✓
#   [TEST 1.4] Migration Verification... ✓
#
#   ✅ Module 1: PASS
```

### Phase 3: Review Test Report

```powershell
# Open the generated report
notepad module1_test_report.md

# Or view in VS Code
code module1_test_report.md
```

---

## Module Testing Sequence

### Module 1: Database Testing ✅ READY
**File:** `run-module1-tests.ps1`  
**Status:** Script prepared, awaiting Docker fix  
**Duration:** ~2 minutes  
**Prerequisites:** Docker + PostgreSQL running  
**On Success:** Proceed to Module 2

### Module 2: Backend API Testing ⏳ PREPARED
**Will test:** FastAPI backend on port 5000  
**Prerequisites:** Module 1 PASS + Backend code + Auth service running  
**Expected tests:**
- API endpoint responses
- JWT authentication
- Error handling
- Database integration

### Module 3: AI Agent Testing ⏳ PREPARED
**Will test:** RAG service on port 5002  
**Prerequisites:** Modules 1-2 PASS + RAG service code  
**Expected tests:**
- Agent response functionality
- RAG/Semantic search
- Guardrails & safety
- Fallback logic

### Module 4: Frontend Testing ⏳ PREPARED
**Will test:** React/Next.js on port 3000  
**Prerequisites:** Modules 1-3 PASS + Frontend code  
**Expected tests:**
- Page rendering
- API integration
- Authentication flow
- Unit tests & builds

### Integration Testing ⏳ PREPARED
**Will test:** Complete system  
**Prerequisites:** ALL 4 modules PASS  
**Expected tests:**
- Full workflow execution
- Data persistence
- Cross-service communication
- Performance baselines

---

## Quick Troubleshooting

### Docker won't start at all

```powershell
# Check Docker Desktop logs
$logPath = "$env:APPDATA\Docker\log.txt"
Get-Content $logPath -Tail 50

# Restart Windows
Restart-Computer

# Or reinstall Docker
# Download from: https://www.docker.com/products/docker-desktop
```

### Containers start but healthcheck fails

```powershell
# Check container logs
docker logs ai_ba_postgres
docker logs ai_ba_redis
docker logs ai_ba_qdrant

# Check if ports are in use
netstat -ano | findstr ":5432"  # PostgreSQL
netstat -ano | findstr ":6379"  # Redis
netstat -ano | findstr ":6333"  # Qdrant
```

### Tests fail with "container not running"

```powershell
# Verify containers are actually running
docker ps

# If not showing up, start them explicitly
docker-compose up -d postgres

# Check exit code
docker ps -a | grep ai_ba_postgres

# View logs for errors
docker logs ai_ba_postgres --tail 50
```

---

## Testing Timeline

| Time | Activity | Module |
|------|----------|--------|
| T+0 min | Docker fix + infrastructure start | Prep |
| T+5 min | Module 1 Database tests | ✅ |
| T+7 min | Review Module 1 report | Review |
| T+10 min | Module 2 Backend tests (if code ready) | ⏳ |
| T+12 min | Review Module 2 report | Review |
| T+15 min | Module 3 AI Agent tests | ⏳ |
| T+17 min | Review Module 3 report | Review |
| T+20 min | Module 4 Frontend tests | ⏳ |
| T+22 min | Review Module 4 report | Review |
| T+25 min | Integration testing | ⏳ |
| **T+30 min** | **SYSTEM READY FOR PRODUCTION** | ✅ |

---

## Next Steps

1. **Immediate (Now):** Fix Docker Desktop using steps above
2. **When Docker is fixed:** Run `.\run-module1-tests.ps1`
3. **Review report:** Check `module1_test_report.md` for PASS/FAIL status
4. **On PASS:** Proceed to Module 2 (Backend testing)
5. **On FAIL:** Fix issues and re-run Module 1

---

**Document Version:** 1.0  
**Created:** 2026-03-17  
**Project:** AI 智能業務助理 Testing Execution
