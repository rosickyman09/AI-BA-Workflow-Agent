@echo off
REM ============================================================================
REM Stop All Services - AI BA Agent Deployment Script (Windows)
REM ============================================================================
REM This script gracefully stops all containerized services
REM ============================================================================

setlocal enabledelayedexpansion
set "COMPOSE_DIR=%~dp0.."

REM Color codes (Windows 10+)
set "BLUE=[36m"
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "NC=[0m"

echo.
echo "%BLUE%============================================================================%NC%"
echo "%BLUE%Stopping AI BA Agent Services%NC%"
echo "%BLUE%============================================================================%NC%"
echo.

REM Check if docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo "%YELLOW%⚠ Warning: docker is not installed or not in PATH%NC%"
    exit /b 0
)

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo "%YELLOW%⚠ Warning: docker-compose is not installed or not in PATH%NC%"
    exit /b 0
)

REM Check if any containers are running
cd "%COMPOSE_DIR%"
docker-compose ps 2>nul | find "ai_ba" >nul
if errorlevel 1 (
    echo "%YELLOW%ℹ No AI BA Agent containers currently running%NC%"
    exit /b 0
)

echo "%YELLOW%Stopping all services (gracefully)...%NC%"
call docker-compose down
if errorlevel 1 (
    echo "%RED%❌ Failed to stop services%NC%"
    exit /b 1
)

echo.
echo "%GREEN%============================================================================%NC%"
echo "%GREEN%✅ All services stopped successfully%NC%"
echo "%GREEN%============================================================================%NC%"
echo.
echo "Note: Data in volumes has been preserved"
echo "To remove ALL data including volumes, run: docker-compose down -v"
echo.

endlocal
