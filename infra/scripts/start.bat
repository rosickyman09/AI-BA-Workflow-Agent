@echo off
REM ============================================================================
REM Start All Services - AI BA Agent Deployment Script (Windows)
REM ============================================================================
REM This script starts all containerized services in the correct order:
REM 1. Database & Infrastructure (postgres, redis, qdrant)
REM 2. Backend Services (auth_service, backend, rag_service)
REM 3. Frontend & Gateway (frontend, gateway)
REM ============================================================================

setlocal enabledelayedexpansion
set "COMPOSE_DIR=%~dp0.."
set "MAX_RETRIES=60"
set "RETRY_INTERVAL=2"

REM Color codes (Windows 10+)
set "BLUE=[36m"
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "NC=[0m"

echo.
echo "%BLUE%============================================================================%NC%"
echo "%BLUE%Starting AI BA Agent Services%NC%"
echo "%BLUE%============================================================================%NC%"
echo.

REM Check if docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo "%RED%❌ Error: docker is not installed or not in PATH%NC%"
    exit /b 1
)

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo "%RED%❌ Error: docker-compose is not installed or not in PATH%NC%"
    exit /b 1
)

echo "%YELLOW%[1/4] Building Docker images...%NC%"
cd "%COMPOSE_DIR%"
call docker-compose build
if errorlevel 1 (
    echo "%RED%❌ Failed to build images%NC%"
    exit /b 1
)
echo "%GREEN%✓ Images built successfully%NC%"
echo.

echo "%YELLOW%[2/4] Starting infrastructure services (postgres, redis, qdrant)...%NC%"
call docker-compose up -d postgres redis qdrant
echo "%GREEN%✓ Infrastructure services started%NC%"
echo.

echo "%YELLOW%[3/4] Waiting for infrastructure services to be healthy...%NC%"
for %%s in (postgres redis qdrant) do (
    echo "  Waiting for %%s...%NC%"
    set "RETRIES=0"
    :wait_loop_%%s
    if !RETRIES! geq %MAX_RETRIES% (
        echo "%RED%❌ Service %%s failed to become healthy%NC%"
        exit /b 1
    )
    docker-compose ps %%s 2>nul | find "healthy" >nul
    if errorlevel 1 (
        set /a "RETRIES+=1"
        if !RETRIES! equ 10 echo -n "."
        timeout /t %RETRY_INTERVAL% /nobreak >nul 2>&1
        goto wait_loop_%%s
    )
    echo "%GREEN%✓%NC%"
)
echo.

echo "%YELLOW%[4/4] Starting application services (auth, backend, rag, frontend, gateway)...%NC%"
call docker-compose up -d auth_service backend rag_service frontend gateway
echo "%GREEN%✓ Application services started%NC%"
echo.

echo "%YELLOW%Verifying service health...%NC%"
echo.
echo "Container Status:"
call docker-compose ps
echo.

echo "%GREEN%============================================================================%NC%"
echo "%GREEN%✅ AI BA Agent services started successfully!%NC%"
echo "%GREEN%============================================================================%NC%"
echo.
echo "Access points:"
echo "  Frontend:       http://localhost:3000"
echo "  Backend API:    http://localhost:5000/health"
echo "  Auth Service:   http://localhost:5001/health"
echo "  RAG Service:    http://localhost:5002/health"
echo "  Database:       localhost:5432"
echo "  Redis:          localhost:6379"
echo "  Qdrant:         http://localhost:6333"
echo.
echo "View logs:"
echo "  docker-compose logs -f [service]"
echo.

endlocal
