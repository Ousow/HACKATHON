"""
DAG Airflow — Pipeline HACKATHON 2026
======================================
Architecture réelle du projet :
  MinIO (Raw Zone)
      → OCR (Tesseract via ocr-app)        → MinIO (Clean Zone : texte extrait)
      → Validation (validation-service)    → MinIO (Curated Zone : JSON validé)

Déclencheur  : Toutes les 5 min — détecte un nouvel objet dans MinIO "raw"
Orchestration : Séquentielle
Services     : MinIO (S3), ocr-app (Tesseract + field_extractor), validation-service (FastAPI :8001)

Zones MinIO :
  raw      — PDFs bruts uploadés (upload_raw.py)
  clean    — Textes OCR extraits .txt (save_clean.py)
  curated  — JSON structurés + résultats validation (save_curated.py)

Pour déployer :
  1. Copier ce fichier dans le dossier /dags/ de votre Airflow
  2. Ajuster les Variables Airflow si besoin (Admin → Variables)
  3. S'assurer que validation-service tourne sur le port 8001
"""
// start_airflow.ps1 — Lance la stack complete HACKATHON + Airflow sur Windows
commande
# Usage : powershell -ExecutionPolicy Bypass -File .\start_airflow.ps1
# ─────────────────────────────────────────────────────────────────────────────
# HACKATHON 2026 — Stack complète avec Airflow
# ─────────────────────────────────────────────────────────────────────────────
# Usage :
#   Première fois   : docker-compose -f docker-compose.airflow.yml up airflow-init
#   Lancer la stack : docker-compose -f docker-compose.airflow.yml up -d
#   UI Airflow      : http://localhost:8080  (admin / admin)
#   UI MinIO        : http://localhost:9001  (minioadmin / minioadmin)
#   Validation API  : http://localhost:8001/docs
