# Automated VPS Deployment Runner
$VpsIp = "31.6.62.193"
$VpsUser = "root"
$RemoteDir = "/root/shop-bot"
$LocalDir = $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  🚀 KDS Digital Store - VPS Cloud Deployment" -ForegroundColor Green
Write-Host "  Target VPS IP: $VpsIp" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

# Step 1: Ensure directory
Write-Host "`n[1/3] Ensuring remote folder exists..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no "${VpsUser}@${VpsIp}" "mkdir -p ${RemoteDir}"

# Step 2: SCP Project files
Write-Host "`n[2/3] Transferring project codebase to VPS..." -ForegroundColor Yellow
scp -r -o StrictHostKeyChecking=no "$LocalDir/apps" "$LocalDir/packages" "$LocalDir/bot.py" "$LocalDir/run_api.py" "$LocalDir/notify_bot.py" "$LocalDir/clean_sync.py" "$LocalDir/docker-compose.yml" "$LocalDir/docker-compose.prod.yml" "$LocalDir/Caddyfile" "$LocalDir/Dockerfile" "$LocalDir/requirements.txt" "$LocalDir/package.json" "$LocalDir/.env" "$LocalDir/deploy_vps.sh" "${VpsUser}@${VpsIp}:${RemoteDir}/"

# Step 3: Run deploy script
Write-Host "`n[3/3] Executing fresh container build & launch on VPS..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no "${VpsUser}@${VpsIp}" "chmod +x ${RemoteDir}/deploy_vps.sh && bash ${RemoteDir}/deploy_vps.sh"

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "  🎉 VPS DEPLOYMENT COMPLETED!" -ForegroundColor Green
Write-Host "  🌐 Website:     https://kalidigitalstore.page.gd" -ForegroundColor Cyan
Write-Host "  🖥️ Direct VPS:  http://${VpsIp}" -ForegroundColor Cyan
Write-Host "  📊 Admin:       http://${VpsIp}/admin" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Green
