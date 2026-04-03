#!/bin/bash
# ============================================================================
# Stop All Services - AI BA Agent Deployment Script
# ============================================================================
# This script gracefully stops all containerized services
# Services are stopped in reverse order of their dependencies:
# 1. Gateway & Frontend (dependent on everything)
# 2. Backend Services (auth_service, backend, rag_service)
# 3. Infrastructure (postgres, redis, qdrant)
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

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Stopping AI BA Agent Services${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if docker and docker-compose are available
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠ Warning: docker is not installed or not in PATH${NC}"
    exit 0
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠ Warning: docker-compose is not installed or not in PATH${NC}"
    exit 0
fi

# Check if any containers are running
if ! docker-compose -f "$DOCKER_COMPOSE_FILE" ps | grep -q "ai_ba"; then
    echo -e "${YELLOW}ℹ No AI BA Agent containers currently running${NC}"
    exit 0
fi

cd "$COMPOSE_DIR"

echo -e "${YELLOW}Stopping all services (gracefully)...${NC}"
docker-compose down

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}✅ All services stopped successfully${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "Note: Data in volumes has been preserved"
echo -e "To remove ALL data including volumes, run: ${BLUE}docker-compose down -v${NC}"
echo ""
