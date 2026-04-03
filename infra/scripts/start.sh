#!/bin/bash
# ============================================================================
# Start All Services - AI BA Agent Deployment Script
# ============================================================================
# This script starts all containerized services in the correct order:
# 1. Database & Infrastructure (postgres, redis, qdrant)
# 2. Backend Services (auth_service, backend, rag_service)
# 3. Frontend & Gateway (frontend, gateway)
#
# Health checks ensure each service is ready before dependent services start
# ============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"
MAX_RETRIES=60
RETRY_INTERVAL=2

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Starting AI BA Agent Services${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if docker and docker-compose are available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: docker is not installed${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Error: docker-compose is not installed${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/4] Building Docker images...${NC}"
cd "$COMPOSE_DIR"
docker-compose build
echo -e "${GREEN}✓ Images built successfully${NC}"
echo ""

echo -e "${YELLOW}[2/4] Starting infrastructure services (postgres, redis, qdrant)...${NC}"
docker-compose up -d postgres redis qdrant
echo -e "${GREEN}✓ Infrastructure services started${NC}"
echo ""

# Wait for infrastructure to be healthy
echo -e "${YELLOW}[3/4] Waiting for infrastructure services to be healthy...${NC}"
for service in postgres redis qdrant; do
    echo -n "  Waiting for $service... "
    RETRIES=0
    while [ $RETRIES -lt $MAX_RETRIES ]; do
        if docker-compose ps $service | grep -q "healthy"; then
            echo -e "${GREEN}✓${NC}"
            break
        fi
        RETRIES=$((RETRIES + 1))
        if [ $((RETRIES % 10)) -eq 0 ]; then
            echo -n "."
        fi
        sleep $RETRY_INTERVAL
    done
    if [ $RETRIES -eq $MAX_RETRIES ]; then
        echo ""
        echo -e "${RED}❌ Service $service failed to become healthy${NC}"
        exit 1
    fi
done
echo ""

echo -e "${YELLOW}[4/4] Starting application services (auth, backend, rag, frontend, gateway)...${NC}"
docker-compose up -d auth_service backend rag_service frontend gateway
echo -e "${GREEN}✓ Application services started${NC}"
echo ""

# Wait for all services to be healthy
echo -e "${YELLOW}Waiting for all services to be healthy...${NC}"
ALL_SERVICES=(postgres redis qdrant auth_service backend rag_service frontend gateway)
for service in "${ALL_SERVICES[@]}"; do
    echo -n "  Waiting for $service... "
    RETRIES=0
    while [ $RETRIES -lt $MAX_RETRIES ]; do
        HEALTH=$(docker-compose ps $service 2>/dev/null | grep -c "healthy" || echo "0")
        if [ $HEALTH -gt 0 ]; then
            echo -e "${GREEN}✓${NC}"
            break
        fi
        RETRIES=$((RETRIES + 1))
        if [ $((RETRIES % 10)) -eq 0 ]; then
            echo -n "."
        fi
        sleep $RETRY_INTERVAL
    done
    if [ $RETRIES -eq $MAX_RETRIES ]; then
        echo ""
        echo -e "${YELLOW}⚠ Service $service did not become healthy (may still be starting)${NC}"
    fi
done
echo ""

# Verify startup with health checks
echo -e "${YELLOW}Verifying service health...${NC}"
echo ""

echo "Container Status:"
docker-compose ps
echo ""

# Test health endpoints
echo -e "${YELLOW}Testing service health endpoints...${NC}"
echo ""

HEALTH_CHECKS=(
    "postgresql:postgres@postgresql:5432|Database"
    "http://localhost:5001/health|Auth Service"
    "http://localhost:5000/health|Backend API"
    "http://localhost:5002/health|RAG Service"
    "http://localhost:3000|Frontend"
    "http://localhost:80|Gateway"
)

for check in "${HEALTH_CHECKS[@]}"; do
    IFS='|' read -r endpoint name <<< "$check"
    
    if [[ $endpoint == *"postgresql"* ]]; then
        echo -n "  Testing $name... "
        if docker-compose exec -T postgres pg_isready -U postgres -d ai_ba_db &> /dev/null; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${YELLOW}⚠ (still starting)${NC}"
        fi
    else
        echo -n "  Testing $name... "
        if curl -f -s "$endpoint" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${YELLOW}⚠ (still starting)${NC}"
        fi
    fi
done

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}✅ AI BA Agent services started successfully!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "Access points:"
echo -e "  Frontend:       ${BLUE}http://localhost:3000${NC}"
echo -e "  Backend API:    ${BLUE}http://localhost:5000/health${NC}"
echo -e "  Auth Service:   ${BLUE}http://localhost:5001/health${NC}"
echo -e "  RAG Service:    ${BLUE}http://localhost:5002/health${NC}"
echo -e "  Database:       ${BLUE}localhost:5432${NC}"
echo -e "  Redis:          ${BLUE}localhost:6379${NC}"
echo -e "  Qdrant:         ${BLUE}http://localhost:6333${NC}"
echo ""
echo -e "View logs:"
echo -e "  ${BLUE}docker-compose logs -f [service]${NC}"
echo ""
