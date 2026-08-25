#!/bin/bash
# ==============================================================================
# Fresh Deploy Script for Shop Bot
# Run on VPS from /root/shop-bot:
#   cd /root/shop-bot && bash scripts/fresh_deploy.sh
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
step()    { echo -e "\n${BLUE}══════════════════════════════════════${NC}"; echo -e "${BLUE}  $*${NC}"; echo -e "${BLUE}══════════════════════════════════════${NC}"; }

COMPOSE="docker compose -f docker-compose.prod.yml"
APP_DIR="/root/shop-bot"

step "Step 1/7: Pre-flight checks"
cd "$APP_DIR"

# Check .env exists
if [ ! -f ".env" ]; then
    error ".env file not found at $APP_DIR/.env"
    echo "Please create .env from .env.example and fill in your credentials"
    exit 1
fi
success ".env found"

# Check Docker is running
if ! docker info &>/dev/null; then
    error "Docker is not running"
    exit 1
fi
success "Docker is running"

step "Step 2/7: Wipe ALL existing Docker resources (fresh start)"
warn "Stopping and removing ALL containers, images, and volumes..."

# Stop all running containers
if [ "$(docker ps -q)" ]; then
    docker stop $(docker ps -q) && info "Stopped all running containers"
fi

# Remove all containers
if [ "$(docker ps -aq)" ]; then
    docker rm -f $(docker ps -aq) && info "Removed all containers"
fi

# Remove shop-bot volumes (data wipe — fresh start as requested)
docker volume ls -q | grep -E "shop.bot_|shopbot_" | xargs docker volume rm -f 2>/dev/null || true

# Remove ALL Docker images to force fresh build
docker image prune -af && info "Removed all images"

# System cleanup
docker system prune -af --volumes 2>/dev/null || true

success "Docker environment wiped clean"

step "Step 3/7: Fix file permissions"
# Ensure the entrypoint is executable (git may not preserve this on Windows)
chmod +x docker-entrypoint.sh
chmod +x scripts/*.sh 2>/dev/null || true
success "Permissions set"

step "Step 4/7: Build Docker images"
info "Building all images (this takes ~5-10 minutes on first run)..."
info "Note: Node.js build may take 3-5 minutes — this is normal"
$COMPOSE build --no-cache --parallel
success "All images built"

step "Step 5/7: Start infrastructure (db + redis)"
info "Starting database and redis..."
$COMPOSE up -d db redis
info "Waiting for database to be healthy..."

# Wait up to 60 seconds for db to be ready
timeout=60
elapsed=0
while ! docker compose -f docker-compose.prod.yml exec -T db pg_isready -U "${POSTGRES_USER:-shop_user}" &>/dev/null; do
    sleep 2
    elapsed=$((elapsed + 2))
    if [ $elapsed -ge $timeout ]; then
        error "Database did not become healthy within ${timeout}s"
        $COMPOSE logs db
        exit 1
    fi
    echo -n "."
done
echo ""
success "Database is ready"

step "Step 6/7: Run database migrations"
info "Running Alembic migrations..."
$COMPOSE run --rm \
    -e POSTGRES_HOST=db \
    -e DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER:-shop_user}:${POSTGRES_PASSWORD:-KaliShop_Secure_2026}@db:5432/${POSTGRES_DB:-telegram_shop}" \
    bot alembic upgrade head
success "Database migrations complete"

step "Step 7/7: Start all services"
info "Starting all services..."
$COMPOSE up -d
info "Waiting 30 seconds for services to stabilise..."
sleep 30

# ── Final status ──────────────────────────────────────────────────────────────
step "Deployment Status"
$COMPOSE ps

echo ""
info "Checking service health..."

# API health check
if curl -sf http://localhost:8000/health &>/dev/null 2>&1; then
    success "API is responding"
elif curl -sf http://localhost/api/health &>/dev/null 2>&1; then
    success "API (via Caddy) is responding"
else
    warn "API health check failed — check logs: $COMPOSE logs api"
fi

# Bot admin panel (internal)
if curl -sf http://localhost:9090/health &>/dev/null 2>&1; then
    success "Bot admin panel is responding on port 9090"
else
    warn "Bot admin panel not yet responding (may still be starting)"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo "  Bot:         Telegram (polling mode)"
echo "  API:         http://20.164.209.124/api/health"
echo "  Web:         http://20.164.209.124/"
echo "  Admin Panel: Access via SSH tunnel:"
echo "               ssh -L 9090:localhost:9090 root@20.164.209.124"
echo "               Then open: http://localhost:9090"
echo "  Admin login: prabin / KaliAdmin2028"
echo ""
echo "  Logs:        docker compose -f docker-compose.prod.yml logs -f"
echo "  Status:      docker compose -f docker-compose.prod.yml ps"
echo ""

# DNS reminder
DOMAIN_IP=$(dig +short kalidigitalstore.page.gd 2>/dev/null || echo "unknown")
if [ "$DOMAIN_IP" != "20.164.209.124" ]; then
    warn "DNS: kalidigitalstore.page.gd resolves to '$DOMAIN_IP' (not 20.164.209.124)"
    warn "Update the A record in InfinityFree DNS panel to enable HTTPS."
    warn "Until then, access via http://20.164.209.124"
else
    success "DNS: kalidigitalstore.page.gd points to 20.164.209.124 — HTTPS ready!"
fi
