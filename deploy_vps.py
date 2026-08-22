import os
import sys
import tarfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import paramiko
from scp import SCPClient

VPS_HOST = "31.6.62.193"
VPS_USER = "root"
VPS_PASS = "[REDACTED_PASSWORD]"
REMOTE_DIR = "/root/shop-bot"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

print("========================================================")
print("  KDS Digital Store - Cloud VPS Automated Deployer")
print(f"  Target VPS: {VPS_USER}@{VPS_HOST}")
print(f"  Remote Dir: {REMOTE_DIR}")
print("========================================================")

# Step 1: Package project into a tar archive (excluding caches & node_modules)
tar_path = os.path.join(LOCAL_DIR, "deploy_bundle.tar.gz")
print("\n[1/4] Creating compact deployment bundle...")
exclude_dirs = {"node_modules", ".next", ".git", "venv", ".venv", "__pycache__", ".pytest_cache"}
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
print(f"  [OK] Created bundle: deploy_bundle.tar.gz ({bundle_size:.2f} MB)")

# Step 2: Connect via SSH
print(f"\n[2/4] Connecting to VPS ({VPS_HOST})...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname=VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
print("  [OK] Connected to VPS successfully!")

# Step 3: Upload bundle
print("\n[3/4] Uploading deployment bundle via SCP...")
with SCPClient(ssh.get_transport()) as scp_client:
    ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
    scp_client.put(tar_path, f"{REMOTE_DIR}/deploy_bundle.tar.gz")
print("  [OK] Codebase upload complete!")

if os.path.exists(tar_path):
    os.remove(tar_path)

# Step 4: Extract and Deploy on VPS
print("\n[4/4] Executing fresh container build & deployment on VPS...")
deploy_script = f"""
set -e
cd {REMOTE_DIR}
tar -xzf deploy_bundle.tar.gz
rm -f deploy_bundle.tar.gz

# Ensure Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Ensure Docker Compose plugin is available
if ! docker compose version &> /dev/null; then
    apt-get update -y && apt-get install -y docker-compose-plugin
fi

echo "--- Stopping and removing old containers ---"
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
docker stop $(docker ps -aq) 2>/dev/null || true

echo "--- Building fresh production containers ---"
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

echo "--- Waiting 8s for services initialization ---"
sleep 8

echo "--- Synchronizing verified 4-reseller product catalog on VPS ---"
docker compose -f docker-compose.prod.yml exec -T api python clean_sync.py 2>/dev/null || true

echo "--- Checking live VPS container status ---"
docker compose -f docker-compose.prod.yml ps
"""

stdin, stdout, stderr = ssh.exec_command(deploy_script, get_pty=True)
for line in iter(stdout.readline, ""):
    print(line, end="")

exit_status = stdout.channel.recv_exit_status()
ssh.close()

if exit_status == 0:
    print("\n========================================================")
    print("  [SUCCESS] VPS DEPLOYMENT FULLY COMPLETED!")
    print("  Website:     https://kalidigitalstore.page.gd")
    print(f"  Direct VPS:  http://{VPS_HOST}")
    print(f"  Admin Panel: http://{VPS_HOST}/admin")
    print("========================================================")
else:
    print(f"\n[ERROR] Deployment exited with error code {exit_status}")
    sys.exit(exit_status)
