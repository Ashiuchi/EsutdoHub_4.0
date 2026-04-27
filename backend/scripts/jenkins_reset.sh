#!/usr/bin/env bash
set -euo pipefail

echo "==> Stopping Jenkins container..."
docker compose -f docker-compose.jenkins.yml down --remove-orphans

echo "==> Removing old Jenkins image and container (if any)..."
docker rm -f jenkins 2>/dev/null || true
docker image rm -f "$(docker compose -f docker-compose.jenkins.yml images -q jenkins 2>/dev/null)" 2>/dev/null || true

echo "==> Building new Jenkins image..."
docker compose -f docker-compose.jenkins.yml build --no-cache jenkins

echo "==> Starting Jenkins..."
docker compose -f docker-compose.jenkins.yml up -d

echo ""
echo "Jenkins starting at http://localhost:8085"
echo "Initial admin password (wait ~30s then run):"
echo "  docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword"
