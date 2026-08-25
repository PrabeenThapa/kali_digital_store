#!/bin/bash
# ==============================================================================
# VPS Setup Script for Shop Bot
# Run this script ONCE on a fresh VPS as root:
#   bash scripts/vps_setup.sh
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }

info "=== Kali Digital Store — VPS Setup ==="
info "VPS: 20.164.209.124 | 2 vCPU | 1GB RAM | 30GB SSD"

# ── 1. System update ──────────────────────────────────────────────────────────
info "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget git unzip gnupg2 lsb-release \
    ca-certificates apt-transport-https \
    ufw fail2ban htop

# ── 2. Swap space (critical for 1GB VPS during Docker builds) ─────────────────
if [ ! -f /swapfile ]; then
    info "Creating 2GB swap space..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
    sysctl vm.swappiness=10
    echo 'vm.swappiness=10' | tee -a /etc/sysctl.conf
    success "Swap created: $(free -h | grep Swap)"
else
    warn "Swap already exists, skipping."
fi

# ── 3. Kernel performance tuning ──────────────────────────────────────────────
info "Tuning kernel parameters..."
cat > /etc/sysctl.d/99-shopbot.conf << 'EOF'
# Network performance
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 1024
net.ipv4.tcp_tw_reuse = 1

# Memory
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.overcommit_memory = 1
EOF
sysctl -p /etc/sysctl.d/99-shopbot.conf

# ── 4. Install Docker CE ──────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    info "Installing Docker CE..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
    
    systemctl enable docker
    systemctl start docker
    success "Docker installed: $(docker --version)"
else
    success "Docker already installed: $(docker --version)"
fi

# ── 5. Firewall configuration ─────────────────────────────────────────────────
info "Configuring UFW firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    comment 'SSH'
ufw allow 80/tcp    comment 'HTTP (Caddy)'
ufw allow 443/tcp   comment 'HTTPS (Caddy)'
# Admin panel is NOT exposed publicly — access via SSH tunnel only
echo "y" | ufw enable
success "Firewall configured"

# ── 6. Configure fail2ban (protect SSH) ───────────────────────────────────────
info "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
maxretry = 5
bantime = 3600
findtime = 600
EOF
systemctl enable fail2ban
systemctl restart fail2ban

# ── 7. Set timezone ───────────────────────────────────────────────────────────
timedatectl set-timezone UTC
success "Timezone set to UTC"

# ── 8. Create app directory ───────────────────────────────────────────────────
mkdir -p /root/shop-bot
info "App directory ready at /root/shop-bot"

success "=== VPS setup complete! ==="
echo ""
info "Next steps:"
echo "  1. Upload code:  scp -r \"c:\\Users\\thapa\\OneDrive\\Desktop\\Shop Bot\" root@31.6.62.193:/root/shop-bot"
echo "  2. Deploy:       bash /root/shop-bot/scripts/fresh_deploy.sh"
