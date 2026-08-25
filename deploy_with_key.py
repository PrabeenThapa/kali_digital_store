import os
import sys
import tarfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import paramiko
from scp import SCPClient

VPS_HOST = "31.6.62.193"
VPS_USER = "root"
REMOTE_DIR = "/root/shop-bot"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(LOCAL_DIR, "scratch", "deploy_key")

print("========================================================", flush=True)
print("  KDS Digital Store - Direct Automated Deployment", flush=True)
print(f"  Target VPS: {VPS_USER}@{VPS_HOST}", flush=True)
print("========================================================", flush=True)

# Step 1: Package project into a tar archive
tar_path = os.path.join(LOCAL_DIR, "deploy_bundle.tar.gz")
print("\n[1/4] Creating compact deployment bundle...", flush=True)
exclude_dirs = {"node_modules", ".next", ".git", "venv", ".venv", "__pycache__", ".pytest_cache", "venv_kalibot"}
exclude_exts = {".pyc", ".pyo", ".pyd", ".tar.gz"}

with tarfile.open(tar_path, "w:gz") as tar:
    for item in os.listdir(LOCAL_DIR):
        if item in exclude_dirs or item.endswith(".tar.gz"):
            continue
        full_path = os.path.join(LOCAL_DIR, item)
        def tar_filter(tarinfo):
            name = os.path.basename(tarinfo.name)
            if name in exclude_dirs or any(name.endswith(ext) for ext in exclude_exts):
                return None
            return tarinfo
        tar.add(full_path, arcname=item, filter=tar_filter)

bundle_size = os.path.getsize(tar_path) / (1024 * 1024)
print(f"  [OK] Created bundle: deploy_bundle.tar.gz ({bundle_size:.2f} MB)", flush=True)

# Step 2: Connect via SSH using Deploy Key
print(f"\n[2/4] Connecting to VPS ({VPS_HOST}) using SSH Deploy Key...", flush=True)
private_key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname=VPS_HOST, username=VPS_USER, pkey=private_key, timeout=15)
print("  [OK] Connected to VPS successfully via SSH key!", flush=True)

# Step 3: Upload bundle
print("\n[3/4] Uploading deployment bundle to VPS...", flush=True)
with SCPClient(ssh.get_transport()) as scp_client:
    ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
    scp_client.put(tar_path, f"{REMOTE_DIR}/deploy_bundle.tar.gz")
print("  [OK] Codebase upload complete!", flush=True)

if os.path.exists(tar_path):
    os.remove(tar_path)

# Step 4: Extract and Deploy on VPS
print("\n[4/4] Executing clean build & container launch on VPS...", flush=True)
deploy_script = f"""
set -e
cd {REMOTE_DIR}
tar -xzf deploy_bundle.tar.gz
rm -f deploy_bundle.tar.gz

# Ensure Docker Compose plugin is present
if ! docker compose version &> /dev/null; then
    apt-get update -y && apt-get install -y docker-compose-plugin
fi

echo "-> Stopping old containers..."
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
docker stop $(docker ps -aq) 2>/dev/null || true

echo "-> Building fresh production Docker containers..."
docker compose -f docker-compose.prod.yml build

echo "-> Starting all services in background..."
docker compose -f docker-compose.prod.yml up -d

echo "-> Waiting 12s for database, redis, web & api initialization..."
sleep 12

echo "-> Initializing database and syncing reseller catalog..."
docker compose -f docker-compose.prod.yml exec -T api python clean_sync.py || true

echo "-> Services status:"
docker compose -f docker-compose.prod.yml ps
"""

stdin, stdout, stderr = ssh.exec_command(deploy_script, get_pty=True)
for line in iter(stdout.readline, ""):
    print(f"  {line}", end="", flush=True)

exit_status = stdout.channel.recv_exit_status()
ssh.close()

if exit_status == 0:
    print("\n========================================================", flush=True)
    print("  [SUCCESS] VPS DEPLOYMENT FULLY COMPLETED!", flush=True)
    print("  Website (HTTPS):   https://kalidigitalstore.page.gd", flush=True)
    print(f"  Direct VPS (HTTP): http://{VPS_HOST}", flush=True)
    print(f"  Admin Panel:       http://{VPS_HOST}/admin", flush=True)
    print(f"  API Docs:          http://{VPS_HOST}/docs", flush=True)
    print("========================================================", flush=True)
else:
    print(f"\n[ERROR] Deployment exited with code: {exit_status}", flush=True)
    sys.exit(exit_status)
