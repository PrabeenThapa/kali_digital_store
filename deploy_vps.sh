#!/bin/bash
set -e

REMOTE_DIR="/root/shop-bot"
cd "$REMOTE_DIR"

echo "=== 1. Checking Docker & Compose Installation ==="
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

if ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose plugin..."
    apt-get update -y && apt-get install -y docker-compose-plugin
fi

echo "=== 2. Stopping Old Containers ==="
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
docker stop $(docker ps -aq) 2>/dev/null || true

echo "=== 3. Building and Starting Fresh Containers ==="
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

echo "=== 4. Waiting for Services Initialization ==="
sleep 8

echo "=== 5. Running Clean Reseller Synchronization ==="
docker compose -f docker-compose.prod.yml exec -T api python clean_sync.py 2>/dev/null || true

echo "=== 6. VPS Services Status ==="
docker compose -f docker-compose.prod.yml ps

echo "=================================================="
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "🌐 Domain: https://kalidigitalstore.page.gd"
echo "🖥️ Direct IP: http://31.6.62.193"
echo "=================================================="
