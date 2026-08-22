import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VPS_IP = "31.6.62.193"
VPS_USER = "root"
REMOTE_DIR = "/root/shop-bot"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

print("========================================================")
print("  KDS Digital Store - VPS Cloud Deployment")
print(f"  Target VPS IP: {VPS_IP}")
print("========================================================")

print("\n[1/3] Ensuring remote folder exists...")
res = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", f"{VPS_USER}@{VPS_IP}", f"mkdir -p {REMOTE_DIR}"], capture_output=True, text=True)
print("Remote folder ready!")

print("\n[2/3] Syncing project codebase to VPS via SCP...")
files_to_sync = [
    "apps", "packages", "bot.py", "run_api.py", "notify_bot.py",
    "clean_sync.py", "docker-compose.yml", "docker-compose.prod.yml",
    "Caddyfile", "Dockerfile", "requirements.txt", "package.json", ".env", "deploy_vps.sh"
]

scp_cmd = ["scp", "-r", "-o", "StrictHostKeyChecking=no"] + [os.path.join(LOCAL_DIR, f) for f in files_to_sync] + [f"{VPS_USER}@{VPS_IP}:{REMOTE_DIR}/"]
res_scp = subprocess.run(scp_cmd, capture_output=True, text=True)
if res_scp.returncode != 0:
    print(f"SCP Output/Error: {res_scp.stderr}")
else:
    print("Codebase transferred successfully!")

print("\n[3/3] Executing fresh production container build & restart on VPS...")
deploy_cmd = f"chmod +x {REMOTE_DIR}/deploy_vps.sh && bash {REMOTE_DIR}/deploy_vps.sh"
res_deploy = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", f"{VPS_USER}@{VPS_IP}", deploy_cmd], text=True)

if res_deploy.returncode == 0:
    print("\n========================================================")
    print("  [SUCCESS] VPS DEPLOYMENT FULLY COMPLETED!")
    print("  Website:     https://kalidigitalstore.page.gd")
    print(f"  Direct VPS:  http://{VPS_IP}")
    print(f"  Admin Panel: http://{VPS_IP}/admin")
    print("========================================================")
else:
    print(f"\n[ERROR] Deployment failed with code {res_deploy.returncode}")
