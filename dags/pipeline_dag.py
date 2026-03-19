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

from __future__ import annotations

import io
import json
import sys
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable

import logging
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — modifiable via l'UI Airflow (Admin → Variables)
# ─────────────────────────────────────────────────────────────────────────────

MINIO_ENDPOINT         = Variable.get("minio_endpoint",          default_var="localhost:9000")
MINIO_USER             = Variable.get("minio_user",              default_var="minioadmin")
MINIO_PASSWORD         = Variable.get("minio_password",          default_var="minioadmin")
VALIDATION_SERVICE_URL = Variable.get("validation_service_url",  default_var="http://localhost:8001")
OCR_SERVICE_URL        = Variable.get("ocr_service_url",         default_var="http://localhost:8002")

# Buckets MinIO (les 3 zones du Datalake — init_zones.py)
BUCKET_RAW     = "raw"
BUCKET_CLEAN   = "clean"
BUCKET_CURATED = "curated"

# Chemin local vers les modules du projet
PROJECT_ROOT = Variable.get("project_root", default_var="/app")

DEFAULT_ARGS = {
    "owner"           : "data-team",
    "depends_on_past" : False,
    "start_date"      : datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry"  : False,
    "retries"         : 2,
    "retry_delay"     : timedelta(minutes=3),
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS MINIO
# ─────────────────────────────────────────────────────────────────────────────

def get_minio_client():
    """Crée et retourne un client MinIO (identique à pipeline.py::get_minio_client)."""
    from minio import Minio
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_USER,
        secret_key=MINIO_PASSWORD,
        secure=False,
    )
    client.list_buckets()   # lève une exception si non joignable
    return client


def ensure_buckets(client):
    """Crée les 3 zones si elles n'existent pas encore (init_zones.py)."""
    for bucket in [BUCKET_RAW, BUCKET_CLEAN, BUCKET_CURATED]:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info(f"[MINIO] Bucket créé : {bucket}")


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 1 — Détecter un nouveau fichier dans la Raw Zone
# ─────────────────────────────────────────────────────────────────────────────

def detect_new_file_in_raw(**context):
    """
    Scanne le bucket MinIO 'raw' pour trouver les PDFs non encore traités.
    Compare avec la liste déjà traitée stockée en Variable Airflow.
    Pousse le nom de l'objet détecté dans XCom.
    """
    client = get_minio_client()
    ensure_buckets(client)

    # Récupérer la liste des fichiers déjà traités
    try:
        already_processed = json.loads(
            Variable.get("pipeline_processed_files", default_var="[]")
        )
    except Exception:
        already_processed = []

    # Lister les objets dans raw/
    objects = list(client.list_objects(BUCKET_RAW, recursive=True))
    pdf_objects = [
        obj.object_name for obj in objects
        if obj.object_name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".tiff"))
    ]

    # Trouver le premier fichier non traité
    new_files = [f for f in pdf_objects if f not in already_processed]

    if not new_files:
        raise ValueError(
            f"Aucun nouveau fichier dans MinIO bucket '{BUCKET_RAW}'. "
            "Uploadez un PDF avec : python Datalake/upload_raw.py <fichier.pdf>"
        )

    # Prendre le plus ancien (ordre alphabétique ~ chronologique par date dans le nom)
    target_object = sorted(new_files)[0]
    filename = Path(target_object).name

    logger.info(f"[DETECT] Nouvel objet détecté : {target_object}")

    context["ti"].xcom_push(key="object_name", value=target_object)
    context["ti"].xcom_push(key="filename",    value=filename)
    context["ti"].xcom_push(key="scenario_id", value=Path(filename).stem)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 2 — Télécharger le fichier depuis Raw Zone
# ─────────────────────────────────────────────────────────────────────────────

def download_from_raw(**context):
    """
    Télécharge le PDF depuis MinIO raw/ vers un fichier temporaire local.
    Nécessaire pour que Tesseract puisse lire le fichier (inverse de upload_raw.py).
    """
    ti          = context["ti"]
    object_name = ti.xcom_pull(key="object_name", task_ids="detect_new_file_in_raw")
    filename    = ti.xcom_pull(key="filename",    task_ids="detect_new_file_in_raw")

    client = get_minio_client()

    tmp_dir    = tempfile.mkdtemp(prefix="airflow_pipeline_")
    local_path = os.path.join(tmp_dir, filename)

    client.fget_object(BUCKET_RAW, object_name, local_path)
    logger.info(f"[DOWNLOAD] Téléchargé : {object_name} → {local_path}")

    ti.xcom_push(key="local_path", value=local_path)
    ti.xcom_push(key="tmp_dir",    value=tmp_dir)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 3 — OCR (ocr_runner.py + field_extractor.py)
# ─────────────────────────────────────────────────────────────────────────────

def run_ocr(**context):
    """
    Exécute l'OCR Tesseract sur le PDF téléchargé.
    Utilise extract_text_from_pdf() + extract_fields() depuis ocr-app/app/.
    Correspond à run_ocr_local() + process_folder_with_ocr() de pipeline.py.
    Fallback HTTP vers OCR_SERVICE_URL si disponible.
    """
    import httpx

    ti          = context["ti"]
    local_path  = ti.xcom_pull(key="local_path",  task_ids="download_from_raw")
    filename    = ti.xcom_pull(key="filename",     task_ids="detect_new_file_in_raw")
    scenario_id = ti.xcom_pull(key="scenario_id", task_ids="detect_new_file_in_raw")

    ocr_text      = ""
    fields_result = {}

    # ── Tentative 1 : appel HTTP au service ocr-app (si déployé) ──
    try:
        with open(local_path, "rb") as f:
            resp = httpx.post(
                f"{OCR_SERVICE_URL}/process",
                files={"file": (filename, f)},
                timeout=120,
            )
        resp.raise_for_status()
        ocr_response  = resp.json()
        ocr_text      = ocr_response.get("text", "")
        fields_result = ocr_response.get("fields", {})
        logger.info(f"[OCR] Via service HTTP : {len(ocr_text)} caractères extraits")

    except Exception as http_err:
        logger.warning(f"[OCR] Service HTTP indisponible ({http_err}), basculement sur OCR local...")

        # ── Tentative 2 : OCR local Tesseract (ocr_runner.py) ──
        ocr_app_path = os.path.join(PROJECT_ROOT, "ocr-app", "app")
        if ocr_app_path not in sys.path:
            sys.path.insert(0, ocr_app_path)

        from ocr_runner import extract_text_from_pdf
        from field_extractor import extract_fields

        ocr_text      = extract_text_from_pdf(Path(local_path))
        fields_result = extract_fields(ocr_text, filename)
        logger.info(f"[OCR] Local Tesseract : {len(ocr_text)} caractères extraits")

    if not ocr_text:
        raise RuntimeError(f"OCR échoué : aucun texte extrait de {filename}")

    # Type de document et champs extraits
    doc_type = fields_result.get("document_type_guess", "inconnu")
    fields   = fields_result.get("fields", {})
    logger.info(f"[OCR] Type détecté : {doc_type}")

    # Construire extracted_data (même structure que process_folder_with_ocr)
    extracted_data = {
        "scenario_id"       : scenario_id,
        "raw_texts"         : {Path(filename).stem: ocr_text},
        "facture"           : None,
        "attestation_urssaf": None,
        "rib"               : None,
        "kbis"              : None,
        "devis"             : None,
    }

    if doc_type == "facture":
        extracted_data["facture"] = {
            "siret"       : fields.get("siret",        {}).get("value"),
            "tva_intracom": fields.get("tva",          {}).get("value"),
            "iban"        : fields.get("iban",         {}).get("value"),
            "total_ht"    : fields.get("montant_ht",   {}).get("value"),
            "montant_tva" : fields.get("montant_tva",  {}).get("value"),
            "total_ttc"   : fields.get("montant_ttc",  {}).get("value"),
            "date_facture": fields.get("date_emission",{}).get("value"),
        }
    elif doc_type == "attestation":
        extracted_data["attestation_urssaf"] = {
            "siret"              : fields.get("siret",           {}).get("value"),
            "date_debut_validite": fields.get("date_emission",   {}).get("value"),
            "date_fin_validite"  : fields.get("date_expiration", {}).get("value"),
        }
    elif doc_type == "rib":
        extracted_data["rib"] = {
            "iban": fields.get("iban", {}).get("value"),
            "bic" : fields.get("bic",  {}).get("value"),
        }
    elif doc_type == "devis":
        extracted_data["devis"] = {
            "siret"    : fields.get("siret",       {}).get("value"),
            "total_ht" : fields.get("montant_ht",  {}).get("value"),
            "total_ttc": fields.get("montant_ttc", {}).get("value"),
        }

    ti.xcom_push(key="ocr_text",       value=ocr_text)
    ti.xcom_push(key="extracted_data", value=extracted_data)
    ti.xcom_push(key="doc_type",       value=doc_type)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 4 — Sauvegarder le texte OCR dans la Clean Zone (save_clean.py)
# ─────────────────────────────────────────────────────────────────────────────

def save_to_clean_zone(**context):
    """
    Sauvegarde le texte OCR brut dans MinIO 'clean/'.
    Identique à save_to_clean() de Datalake/save_clean.py et pipeline.py.
    Format : clean/YYYY-MM-DD/<scenario_id>/<doc_name>.txt
    """
    ti          = context["ti"]
    ocr_text    = ti.xcom_pull(key="ocr_text",    task_ids="run_ocr")
    scenario_id = ti.xcom_pull(key="scenario_id", task_ids="detect_new_file_in_raw")
    filename    = ti.xcom_pull(key="filename",     task_ids="detect_new_file_in_raw")

    client   = get_minio_client()
    today    = datetime.today().strftime("%Y-%m-%d")
    doc_name = Path(filename).stem
    obj_name = f"{today}/{scenario_id}/{doc_name}.txt"

    data = ocr_text.encode("utf-8")
    client.put_object(
        BUCKET_CLEAN, obj_name,
        io.BytesIO(data), len(data),
        content_type="text/plain",
    )
    logger.info(f"[CLEAN] Texte OCR sauvegardé : {BUCKET_CLEAN}/{obj_name}")
    ti.xcom_push(key="clean_object", value=obj_name)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 5 — Appeler le service de validation (validation-service FastAPI :8001)
# ─────────────────────────────────────────────────────────────────────────────

def run_validation(**context):
    """
    Convertit extracted_data vers le format DossierFournisseur attendu par
    POST /validate (validation-service/app/main.py).
    Correspond à convert_extracted_to_validation_request() + call_validation_service()
    de pipeline.py.
    """
    import httpx
    from datetime import date

    ti             = context["ti"]
    extracted_data = ti.xcom_pull(key="extracted_data", task_ids="run_ocr")
    scenario_id    = ti.xcom_pull(key="scenario_id",    task_ids="detect_new_file_in_raw")

    # Construire la requête (même logique que convert_extracted_to_validation_request)
    dossier = {"dossier_id": scenario_id}

    if extracted_data.get("facture"):
        f = extracted_data["facture"]
        dossier["facture"] = {
            "fichier_source" : "facture.pdf",
            "numero_facture" : "INCONNU",
            "siret_emetteur" : f.get("siret")       or "",
            "montant_ht"     : f.get("total_ht")    or 0,
            "taux_tva"       : 0.20,
            "montant_tva"    : f.get("montant_tva") or 0,
            "montant_ttc"    : f.get("total_ttc")   or 0,
            "date_emission"  : f.get("date_facture") or date.today().isoformat(),
            "iban"           : f.get("iban"),
        }

    if extracted_data.get("attestation_urssaf"):
        a = extracted_data["attestation_urssaf"]
        dossier["attestation_urssaf"] = {
            "fichier_source"     : "attestation_urssaf.pdf",
            "numero_attestation" : "",
            "siret"              : a.get("siret")              or "",
            "date_edition"       : a.get("date_debut_validite") or date.today().isoformat(),
            "date_expiration"    : a.get("date_fin_validite")   or date.today().isoformat(),
        }

    if extracted_data.get("rib"):
        r = extracted_data["rib"]
        dossier["rib"] = {
            "fichier_source": "rib.pdf",
            "iban"          : r.get("iban") or "",
            "bic"           : r.get("bic")  or "BNPAFRPP",
            "titulaire"     : "",
        }

    if extracted_data.get("devis"):
        d = extracted_data["devis"]
        dossier["devis"] = {
            "fichier_source": "devis.pdf",
            "numero_devis"  : "INCONNU",
            "siret_emetteur": d.get("siret")     or "",
            "montant_ht"    : d.get("total_ht")  or 0,
            "montant_ttc"   : d.get("total_ttc") or 0,
        }

    request_payload = {"dossier": dossier, "use_ml": False}

    # Appel HTTP → validation-service (FastAPI port 8001)
    try:
        response = httpx.post(
            f"{VALIDATION_SERVICE_URL}/validate",
            json=request_payload,
            timeout=30,
        )
        response.raise_for_status()
        validation_result = response.json()
    except httpx.ConnectError:
        raise RuntimeError(
            f"Service de validation non disponible sur {VALIDATION_SERVICE_URL}. "
            "Lancez : cd validation-service && uvicorn app.main:app --port 8001"
        )

    is_valid  = validation_result.get("est_valide", False)
    score     = validation_result.get("score_confiance", 0)
    anomalies = validation_result.get("anomalies", [])

    logger.info(f"[VALIDATION] Valide={is_valid} | Score={score:.2f} | Anomalies={len(anomalies)}")
    for a in anomalies[:5]:
        logger.warning(f"  • [{a.get('type_anomalie')}] {a.get('message', '')[:80]}")

    ti.xcom_push(key="validation_result", value=validation_result)
    ti.xcom_push(key="is_valid",          value=is_valid)
    ti.xcom_push(key="score",             value=score)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 6 — Branchement selon résultat de validation
# ─────────────────────────────────────────────────────────────────────────────

def branch_on_validation(**context):
    is_valid = context["ti"].xcom_pull(key="is_valid", task_ids="run_validation")
    if is_valid:
        logger.info("[BRANCH] Dossier VALIDE → sauvegarde curated")
        return "save_to_curated_zone"
    else:
        logger.warning("[BRANCH] Dossier INVALIDE → gestion anomalies")
        return "handle_anomalies"


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 7a — Sauvegarder dans la Curated Zone (save_curated.py)
# ─────────────────────────────────────────────────────────────────────────────

def save_to_curated_zone(**context):
    """
    Sauvegarde le JSON structuré + résultat de validation dans MinIO 'curated/'.
    Identique à save_to_minio_curated() de pipeline.py et Datalake/save_curated.py.
    Format : curated/YYYY-MM-DD/validated/<scenario_id>.json
    """
    ti                = context["ti"]
    scenario_id       = ti.xcom_pull(key="scenario_id",       task_ids="detect_new_file_in_raw")
    extracted_data    = ti.xcom_pull(key="extracted_data",     task_ids="run_ocr")
    validation_result = ti.xcom_pull(key="validation_result",  task_ids="run_validation")

    full_result = {
        "scenario_id"      : scenario_id,
        "source"           : "airflow_pipeline",
        "extracted_data"   : {
            "facture"     : extracted_data.get("facture"),
            "attestation" : extracted_data.get("attestation_urssaf"),
            "rib"         : extracted_data.get("rib"),
            "devis"       : extracted_data.get("devis"),
        },
        "validation_result": validation_result,
        "timestamp"        : datetime.now().isoformat(),
        "pipeline_run_id"  : context["run_id"],
    }

    client   = get_minio_client()
    today    = datetime.today().strftime("%Y-%m-%d")
    obj_name = f"{today}/validated/{scenario_id}.json"

    json_bytes = json.dumps(full_result, indent=2, ensure_ascii=False).encode("utf-8")
    client.put_object(
        BUCKET_CURATED, obj_name,
        io.BytesIO(json_bytes), len(json_bytes),
        content_type="application/json",
    )
    logger.info(f"[CURATED] Résultat sauvegardé : {BUCKET_CURATED}/{obj_name}")
    ti.xcom_push(key="curated_object", value=obj_name)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 7b — Gérer les anomalies détectées
# ─────────────────────────────────────────────────────────────────────────────

def handle_anomalies(**context):
    """
    Sauvegarde le dossier invalide dans curated/anomalies/ pour audit humain.
    Logge toutes les anomalies détectées par le validation-service.
    """
    ti                = context["ti"]
    scenario_id       = ti.xcom_pull(key="scenario_id",       task_ids="detect_new_file_in_raw")
    extracted_data    = ti.xcom_pull(key="extracted_data",     task_ids="run_ocr")
    validation_result = ti.xcom_pull(key="validation_result",  task_ids="run_validation")

    anomalies = validation_result.get("anomalies", []) if validation_result else []
    score     = validation_result.get("score_confiance", 0) if validation_result else 0

    logger.warning(f"[ANOMALIES] {len(anomalies)} anomalie(s) pour {scenario_id}")
    for a in anomalies:
        logger.warning(f"  ⚠️  [{a.get('type_anomalie')}] {a.get('message', '')}")

    # Sauvegarder dans curated/anomalies/ pour traçabilité
    error_report = {
        "scenario_id"      : scenario_id,
        "status"           : "INVALIDE",
        "score_confiance"  : score,
        "anomalies"        : anomalies,
        "extracted_data"   : extracted_data,
        "validation_result": validation_result,
        "failed_at"        : datetime.now().isoformat(),
        "pipeline_run_id"  : context["run_id"],
    }

    try:
        client   = get_minio_client()
        today    = datetime.today().strftime("%Y-%m-%d")
        obj_name = f"{today}/anomalies/{scenario_id}.json"

        json_bytes = json.dumps(error_report, indent=2, ensure_ascii=False).encode("utf-8")
        client.put_object(
            BUCKET_CURATED, obj_name,
            io.BytesIO(json_bytes), len(json_bytes),
            content_type="application/json",
        )
        logger.info(f"[ANOMALIES] Rapport sauvegardé : {BUCKET_CURATED}/{obj_name}")
        ti.xcom_push(key="anomaly_object", value=obj_name)
    except Exception as e:
        logger.error(f"[ANOMALIES] Impossible de sauvegarder le rapport : {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 8 — Marquer le fichier comme traité + cleanup
# ─────────────────────────────────────────────────────────────────────────────

def mark_file_as_processed(**context):
    """
    Ajoute le fichier traité à la liste persistée dans les Variables Airflow.
    Évite de retraiter le même fichier lors du prochain run.
    Nettoie aussi le fichier temporaire local.
    """
    ti          = context["ti"]
    object_name = ti.xcom_pull(key="object_name", task_ids="detect_new_file_in_raw")
    tmp_dir     = ti.xcom_pull(key="tmp_dir",      task_ids="download_from_raw")

    # Mise à jour de la liste des fichiers traités
    try:
        already_processed = json.loads(
            Variable.get("pipeline_processed_files", default_var="[]")
        )
    except Exception:
        already_processed = []

    if object_name not in already_processed:
        already_processed.append(object_name)
        Variable.set("pipeline_processed_files", json.dumps(already_processed))
        logger.info(f"[MARK] Fichier marqué comme traité : {object_name}")

    # Nettoyage du dossier temporaire
    if tmp_dir and os.path.isdir(tmp_dir):
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.info(f"[CLEANUP] Dossier temporaire supprimé : {tmp_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# DÉFINITION DU DAG
# ─────────────────────────────────────────────────────────────────────────────

with DAG(
    dag_id            = "hackathon_pipeline_datalake",
    default_args      = DEFAULT_ARGS,
    description       = "Pipeline HACKATHON 2026 : MinIO Raw → OCR → Validation → Curated",
    schedule_interval = "*/5 * * * *",   # Vérifie toutes les 5 min un nouveau fichier dans MinIO raw
    catchup           = False,
    max_active_runs   = 1,               # Évite les traitements en parallèle
    tags              = ["hackathon", "ocr", "minio", "validation", "datalake"],
) as dag:

    # ── 1. Détecter un nouveau fichier dans MinIO raw/ ──
    detect = PythonOperator(
        task_id         = "detect_new_file_in_raw",
        python_callable = detect_new_file_in_raw,
    )

    # ── 2. Télécharger le PDF depuis MinIO ──
    download = PythonOperator(
        task_id         = "download_from_raw",
        python_callable = download_from_raw,
    )

    # ── 3. OCR (Tesseract + field_extractor) ──
    ocr = PythonOperator(
        task_id         = "run_ocr",
        python_callable = run_ocr,
        retries         = 1,
        retry_delay     = timedelta(minutes=1),
    )

    # ── 4. Sauvegarder le texte OCR dans Clean Zone ──
    save_clean = PythonOperator(
        task_id         = "save_to_clean_zone",
        python_callable = save_to_clean_zone,
    )

    # ── 5. Appeler le validation-service (FastAPI :8001) ──
    validate = PythonOperator(
        task_id         = "run_validation",
        python_callable = run_validation,
        retries         = 1,
    )

    # ── 6. Branchement selon résultat ──
    branch = BranchPythonOperator(
        task_id         = "branch_on_validation",
        python_callable = branch_on_validation,
    )

    # ── 7a. Dossier valide → Curated Zone ──
    save_curated = PythonOperator(
        task_id         = "save_to_curated_zone",
        python_callable = save_to_curated_zone,
    )

    # ── 7b. Dossier invalide → Rapport anomalies ──
    anomalies = PythonOperator(
        task_id         = "handle_anomalies",
        python_callable = handle_anomalies,
    )

    # ── 8. Marquer le fichier comme traité + cleanup /tmp ──
    mark_done = PythonOperator(
        task_id         = "mark_file_as_processed",
        python_callable = mark_file_as_processed,
        trigger_rule    = TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # ── Fin ──
    end = EmptyOperator(
        task_id      = "end",
        trigger_rule = TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # ─────────────────────────────────────────
    # FLUX SÉQUENTIEL
    # ─────────────────────────────────────────
    #
    #  detect_new_file_in_raw          (scan MinIO raw/ → XCom: object_name)
    #         ↓
    #  download_from_raw               (fget_object → /tmp/airflow_pipeline_xxx/)
    #         ↓
    #  run_ocr                         (Tesseract + field_extractor → extracted_data)
    #         ↓
    #  save_to_clean_zone              (MinIO clean/YYYY-MM-DD/<id>/<doc>.txt)
    #         ↓
    #  run_validation                  (POST /validate → validation-service:8001)
    #         ↓
    #  branch_on_validation
    #    ↙ est_valide=True    ↘ est_valide=False
    #  save_to_curated_zone   handle_anomalies
    #  (curated/validated/)   (curated/anomalies/)
    #    ↘                    ↙
    #     mark_file_as_processed       (Variable Airflow + cleanup /tmp)
    #              ↓
    #             end

    detect >> download >> ocr >> save_clean >> validate >> branch
    branch >> [save_curated, anomalies]
    save_curated >> mark_done
    anomalies    >> mark_done
    mark_done    >> end
