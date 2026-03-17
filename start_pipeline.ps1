# ============================================================
#   Script de démarrage du pipeline complet (PowerShell)
#   Hackathon 2026 - Équipe étudiants
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   DEMARRAGE DU PIPELINE HACKATHON 2026" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# Étape 1: Installer les dépendances
Write-Host "[1/5] Installation des dependances..." -ForegroundColor Yellow
Set-Location "$ROOT\dataset"
pip install -r requirements.txt -q 2>$null
Set-Location "$ROOT\validation-service"
pip install -r requirements.txt -q 2>$null
Set-Location $ROOT

# Étape 2: Générer le dataset
Write-Host "[2/5] Generation du dataset..." -ForegroundColor Yellow
Set-Location "$ROOT\dataset"
if (-not (Test-Path "output\labels")) {
    python generate_dataset.py --n_train 20 --n_test 5
} else {
    Write-Host "   Dataset deja present, skip." -ForegroundColor Gray
}
Set-Location $ROOT

# Étape 3: Lancer le service de validation
Write-Host "[3/5] Demarrage du service de validation (port 8001)..." -ForegroundColor Yellow
Set-Location "$ROOT\validation-service"
$job = Start-Job -ScriptBlock {
    Set-Location $using:ROOT\validation-service
    python -m uvicorn app.main:app --port 8001 --host 0.0.0.0
}
Set-Location $ROOT

Write-Host "   Attente du demarrage (5s)..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Vérifier que le service est lancé
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "   Service de validation : OK" -ForegroundColor Green
} catch {
    Write-Host "   Service de validation : En cours de demarrage..." -ForegroundColor Yellow
}

# Étape 4: Lancer le pipeline
Write-Host "[4/5] Execution du pipeline..." -ForegroundColor Yellow
python pipeline.py --scenario 10

# Étape 5: Résumé
Write-Host ""
Write-Host "[5/5] Termine !" -ForegroundColor Green
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   SERVICES DISPONIBLES:" -ForegroundColor Cyan
Write-Host "   - Validation API: http://localhost:8001/docs" -ForegroundColor White
Write-Host "   - MinIO (si lance): http://localhost:9001" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pour arreter le service de validation:" -ForegroundColor Gray
Write-Host "   Stop-Job -Id $($job.Id); Remove-Job -Id $($job.Id)" -ForegroundColor Gray
Write-Host ""
