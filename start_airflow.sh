#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# start_airflow.sh — Lance la stack complète HACKATHON + Airflow
# Usage : bash start_airflow.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

COMPOSE_FILE="docker-compose.airflow.yml"
DAG_FILE="pipeline_dag.py"
DAG_DEST="./dags/pipeline_dag.py"

echo ""
echo "=================================================="
echo "   🚀 HACKATHON 2026 — Démarrage avec Airflow"
echo "=================================================="

# 1. Créer le dossier dags/ et y copier le DAG
echo ""
echo "📁 Étape 1 : Préparation du dossier dags/"
mkdir -p dags logs

if [ -f "$DAG_FILE" ]; then
  cp "$DAG_FILE" "$DAG_DEST"
  echo "   ✅ DAG copié dans dags/"
else
  echo "   ⚠️  Fichier $DAG_FILE introuvable — copiez-le manuellement dans dags/"
fi

# 2. Initialiser Airflow (base de données + user admin)
echo ""
echo "🔧 Étape 2 : Initialisation Airflow (première fois uniquement)..."
docker compose -f "$COMPOSE_FILE" up airflow-init --no-log-prefix 2>&1 | tail -5
echo "   ✅ Airflow initialisé"

# 3. Lancer toute la stack
echo ""
echo "🐳 Étape 3 : Lancement de la stack complète..."
docker compose -f "$COMPOSE_FILE" up -d \
  postgres minio minio-init validation-service ocr-service \
  airflow-webserver airflow-scheduler

echo ""
echo "⏳ Attente du démarrage des services (30 secondes)..."
sleep 30

# 4. Afficher le statut
echo ""
echo "📊 Statut des conteneurs :"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "=================================================="
echo "   ✅ Stack démarrée !"
echo "=================================================="
echo ""
echo "   🌐 Airflow UI        : http://localhost:8080"
echo "      Login             : admin / admin"
echo ""
echo "   🗄️  MinIO UI          : http://localhost:9001"
echo "      Login             : minioadmin / minioadmin"
echo ""
echo "   📋 Validation API    : http://localhost:8001/docs"
echo ""
echo "   📥 Pour uploader un PDF dans la Raw Zone :"
echo "      python Datalake/upload_raw.py <votre_fichier.pdf>"
echo ""
echo "   📜 Pour voir les logs du scheduler :"
echo "      docker logs airflow_scheduler -f"
echo ""
echo "   🛑 Pour tout arrêter :"
echo "      docker compose -f docker-compose.airflow.yml down"
echo "=================================================="
