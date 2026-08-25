import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import paramiko
from scp import SCPClient

VPS_HOST = "31.6.62.193"
USERS_TO_TRY = ["kalidigital", "root"]
PASSWORD = "[REDACTED_PASSWORD]"
REMOTE_DIR = "/root/shop-bot"
GITHUB_REPO = "https://github.com/PrabeenThapa/kali_digital_store.git"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_ENV_PATH = os.path.join(LOCAL_DIR, ".env")

print("========================================================", flush=True)
print("  🚀 KDS Digital Store - Full VPS Clean Slate & Deploy", flush=True)
print(f"  Target VPS Host: {VPS_HOST}", flush=True)
print(f"  GitHub Repo: {GITHUB_REPO}", flush=True)
print("========================================================", flush=True)

# Step 1: Connect via SSH
print("\n[1/6] Connecting to VPS via SSH...", flush=True)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

connected_user = None
for user in USERS_TO_TRY:
    try:
        print(f"  Attempting connection as '{user}'...", flush=True)
        ssh.connect(hostname=VPS_HOST, username=user, password=PASSWORD, timeout=15)
        connected_user = user
        print(f"  [OK] Successfully connected as '{user}'!", flush=True)
        break
    except Exception as e:
        print(f"  Connection as '{user}' failed: {e}", flush=True)

if not connected_user:
    print("[FATAL] Could not authenticate with any user.", flush=True)
    sys.exit(1)

# Step 2: Clean all VPS storage and old docker containers/images
print("\n[2/6] Stopping all containers & cleaning VPS storage...", flush=True)
sudo_prefix = "sudo " if connected_user != "root" else ""

cleanup_script = f"""
set -e
echo "-> Stopping all running docker containers..."
{sudo_prefix}docker stop $({sudo_prefix}docker ps -aq) 2>/dev/null || true
{sudo_prefix}docker rm $({sudo_prefix}docker ps -aq) 2>/dev/null || true

echo "-> Pruning all old images, volumes, and build cache..."
{sudo_prefix}docker system prune -a --volumes -f || true

echo "-> Removing old project directory..."
{sudo_prefix}rm -rf {REMOTE_DIR}
{sudo_prefix}mkdir -p {REMOTE_DIR}
{sudo_prefix}chown -R {connected_user}:{connected_user} {REMOTE_DIR} 2>/dev/null || true

echo "-> Current VPS Disk Space:"
df -h /
"""

stdin, stdout, stderr = ssh.exec_command(cleanup_script, get_pty=True)
for line in iter(stdout.readline, ""):
    print(f"  {line}", end="", flush=True)
stdout.channel.recv_exit_status()

# Step 3: Clone fresh repository from GitHub
print("\n[3/6] Cloning fresh codebase from GitHub...", flush=True)
clone_script = f"""
set -e
{sudo_prefix}git clone {GITHUB_REPO} {REMOTE_DIR}
cd {REMOTE_DIR}
{sudo_prefix}chown -R {connected_user}:{connected_user} {REMOTE_DIR} 2>/dev/null || true
echo "-> Codebase cloned successfully. Commit details:"
git log -1 --oneline
"""
stdin, stdout, stderr = ssh.exec_command(clone_script, get_pty=True)
for line in iter(stdout.readline, ""):
    print(f"  {line}", end="", flush=True)
clone_status = stdout.channel.recv_exit_status()
if clone_status != 0:
    print(f"[ERROR] Failed to clone repo: {clone_status}", flush=True)
    sys.exit(clone_status)

# Step 4: Transfer production .env file
print("\n[4/6] Uploading production .env configuration...", flush=True)
if os.path.exists(LOCAL_ENV_PATH):
    with SCPClient(ssh.get_transport()) as scp_client:
        scp_client.put(LOCAL_ENV_PATH, f"{REMOTE_DIR}/.env")
    print("  [OK] Production .env uploaded successfully!", flush=True)
else:
    print("  [WARNING] Local .env not found!", flush=True)

# Step 5: Build fresh Docker containers and start services
print("\n[5/6] Building fresh production Docker containers (no cache) & launching...", flush=True)
deploy_script = f"""
set -e
cd {REMOTE_DIR}

# Ensure Docker Compose plugin is present
if ! {sudo_prefix}docker compose version &> /dev/null; then
    {sudo_prefix}apt-get update -y && {sudo_prefix}apt-get install -y docker-compose-plugin
fi

echo "-> Building all images..."
{sudo_prefix}docker compose -f docker-compose.prod.yml build --no-cache

echo "-> Starting all services..."
{sudo_prefix}docker compose -f docker-compose.prod.yml up -d

echo "-> Waiting 12s for database, redis, web & api initialization..."
sleep 12

echo "-> Initializing database and syncing reseller catalog..."
{sudo_prefix}docker compose -f docker-compose.prod.yml exec -T api python clean_sync.py || true

echo "-> Running services health check:"
{sudo_prefix}docker compose -f docker-compose.prod.yml ps
"""

stdin, stdout, stderr = ssh.exec_command(deploy_script, get_pty=True)
for line in iter(stdout.readline, ""):
    print(f"  {line}", end="", flush=True)
deploy_status = stdout.channel.recv_exit_status()

# Step 6: Verify Live Status
print("\n[6/6] Checking live connectivity...", flush=True)
verify_script = f"""
cd {REMOTE_DIR}
echo "--- Docker Containers ---"
{sudo_prefix}docker compose -f docker-compose.prod.yml ps
echo "--- Caddy Logs ---"
{sudo_prefix}docker compose -f docker-compose.prod.yml logs --tail 20 caddy || true
echo "--- API Logs ---"
{sudo_prefix}docker compose -f docker-compose.prod.yml logs --tail 20 api || true
echo "--- Bot Logs ---"
{sudo_prefix}docker compose -f docker-compose.prod.yml logs --tail 20 bot || true
"""
stdin, stdout, stderr = ssh.exec_command(verify_script, get_pty=True)
for line in iter(stdout.readline, ""):
    print(f"  {line}", end="", flush=True)
stdout.channel.recv_exit_status()

ssh.close()

if deploy_status == 0:
    print("\n========================================================", flush=True)
    print("  🎉 FRESH VPS DEPLOYMENT COMPLETED SUCCESSFULLY!", flush=True)
    print("  🌐 Website (HTTPS):   https://kalidigitalstore.page.gd", flush=True)
    print(f"  🖥️ Direct VPS (HTTP): http://{VPS_HOST}", flush=True)
    print(f"  📊 Admin Panel:       http://{VPS_HOST}/admin", flush=True)
    print(f"  📚 API Documentation: http://{VPS_HOST}/docs", flush=True)
    print("========================================================", flush=True)
else:
    print(f"\n[ERROR] Deployment failed with exit code: {deploy_status}", flush=True)
    sys.exit(deploy_status)
