# ─────────────────────────────────────────────────────────────────────────────
# start_airflow.ps1 — Lance la stack complete HACKATHON + Airflow sur Windows
# Usage : powershell -ExecutionPolicy Bypass -File .\start_airflow.ps1
# ─────────────────────────────────────────────────────────────────────────────

$COMPOSE_FILE = "docker-compose.airflow.yml"
$DAG_SOURCE   = "pipeline_dag.py"
$DAG_DEST     = ".\dags\pipeline_dag.py"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   HACKATHON 2026 - Demarrage avec Airflow"        -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# -- Etape 1 : Creer les dossiers necessaires --------------------------------
Write-Host ""
Write-Host "Etape 1 : Preparation des dossiers..." -ForegroundColor Yellow

New-Item -ItemType Directory -Force -Path "dags" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
Write-Host "   OK : Dossiers dags/ et logs/ prets" -ForegroundColor Green

# -- Etape 2 : Copier le DAG -------------------------------------------------
Write-Host ""
Write-Host "Etape 2 : Copie du DAG Airflow..." -ForegroundColor Yellow

if (Test-Path $DAG_SOURCE) {
    Copy-Item -Path $DAG_SOURCE -Destination $DAG_DEST -Force
    Write-Host "   OK : pipeline_dag.py copie dans dags/" -ForegroundColor Green
} else {
    Write-Host "   ATTENTION : $DAG_SOURCE introuvable - copiez-le manuellement dans dags/" -ForegroundColor Red
}

# -- Etape 3 : Verifier que Docker est lance ---------------------------------
Write-Host ""
Write-Host "Etape 3 : Verification de Docker..." -ForegroundColor Yellow

$dockerCheck = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ERREUR : Docker n'est pas demarre !" -ForegroundColor Red
    Write-Host "   Ouvrez Docker Desktop puis relancez ce script." -ForegroundColor Red
    Read-Host "Appuyez sur Entree pour quitter"
    exit 1
}
Write-Host "   OK : Docker est en cours d'execution" -ForegroundColor Green

# -- Etape 4 : Initialiser Airflow -------------------------------------------
Write-Host ""
Write-Host "Etape 4 : Initialisation Airflow (premiere fois uniquement)..." -ForegroundColor Yellow

docker compose -f $COMPOSE_FILE up airflow-init --no-log-prefix 2>&1 | Select-Object -Last 5
Write-Host "   OK : Airflow initialise  (login : admin / admin)" -ForegroundColor Green

# -- Etape 5 : Lancer toute la stack -----------------------------------------
Write-Host ""
Write-Host "Etape 5 : Lancement de la stack complete..." -ForegroundColor Yellow

docker compose -f $COMPOSE_FILE up -d postgres minio minio-init validation-service ocr-service airflow-webserver airflow-scheduler

Write-Host "   OK : Tous les services lances" -ForegroundColor Green

# -- Etape 6 : Attendre que les services soient prets ------------------------
Write-Host ""
Write-Host "Etape 6 : Attente du demarrage (30 secondes)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# -- Etape 7 : Afficher le statut --------------------------------------------
Write-Host ""
Write-Host "Statut des conteneurs :" -ForegroundColor Yellow
docker compose -f $COMPOSE_FILE ps

# -- Resume final ------------------------------------------------------------
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   Stack demarree avec succes !"                   -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Airflow UI     : http://localhost:8080"         -ForegroundColor White
Write-Host "   Login          : admin / admin"                 -ForegroundColor Gray
Write-Host ""
Write-Host "   MinIO UI       : http://localhost:9001"         -ForegroundColor White
Write-Host "   Login          : minioadmin / minioadmin"       -ForegroundColor Gray
Write-Host ""
Write-Host "   Validation API : http://localhost:8001/docs"    -ForegroundColor White
Write-Host ""
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
Write-Host "   Pour uploader un PDF et declencher le pipeline :"  -ForegroundColor Yellow
Write-Host "   python Datalake\upload_raw.py MON_FICHIER.pdf"     -ForegroundColor White
Write-Host ""
Write-Host "   Pour voir les logs du scheduler :"              -ForegroundColor Yellow
Write-Host "   docker logs airflow_scheduler -f"               -ForegroundColor White
Write-Host ""
Write-Host "   Pour tout arreter :"                            -ForegroundColor Yellow
Write-Host "   docker compose -f docker-compose.airflow.yml down" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Ouvrir automatiquement l'UI Airflow dans le navigateur
$openBrowser = Read-Host "Ouvrir Airflow dans le navigateur ? (o/n)"
if ($openBrowser -eq "o" -or $openBrowser -eq "O") {
    Start-Process "http://localhost:8080"
}
