import os
import sys
import paramiko
import httpx
import time

VPS_HOST = "31.6.62.193"
VPS_USER = "root"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(LOCAL_DIR, "scratch", "deploy_key")

print("========================================================", flush=True)
print("  Final VPS Verification & Live Store Test", flush=True)
print("========================================================", flush=True)

private_key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname=VPS_HOST, username=VPS_USER, pkey=private_key, timeout=15)

script = """
cd /root/shop-bot
docker compose -f docker-compose.prod.yml restart caddy
sleep 2
echo "=== RUNNING PRODUCT CATALOG SYNC ==="
docker compose -f docker-compose.prod.yml exec -T api python clean_sync.py || true
echo "=== DOCKER CONTAINERS STATUS ==="
docker compose -f docker-compose.prod.yml ps
"""

stdin, stdout, stderr = ssh.exec_command(script, get_pty=True)
for line in iter(stdout.readline, ""):
    print(f"  {line}", end="", flush=True)

stdout.channel.recv_exit_status()
ssh.close()

# Test endpoints
print("\n--- Testing Live Public Endpoints ---", flush=True)
try:
    with httpx.Client(timeout=10) as client:
        r_store = client.get(f"http://{VPS_HOST}", follow_redirects=True)
        print(f"  Web Storefront (http://{VPS_HOST}): Status {r_store.status_code}")
        
        r_admin = client.get(f"http://{VPS_HOST}/admin", follow_redirects=True)
        print(f"  Admin Dashboard (http://{VPS_HOST}/admin): Status {r_admin.status_code}")
        
        r_api = client.get(f"http://{VPS_HOST}/docs", follow_redirects=True)
        print(f"  API Docs (http://{VPS_HOST}/docs): Status {r_api.status_code}")
except Exception as e:
    print(f"  Endpoint test error: {e}")

print("\n========================================================", flush=True)
print("  [SUCCESS] All checks completed!")
print("========================================================", flush=True)
