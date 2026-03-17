"""
Pipeline d'intégration - Communication entre tous les composants.

Ce script orchestre :
1. Lecture depuis MinIO (Raw Zone) ou Dataset local
2. Appel à l'OCR (Tesseract)
3. Appel au service de Validation (ton module)
4. Sauvegarde dans MinIO (Clean + Curated zones)

Usage:
    python pipeline.py                    # Pipeline complet
    python pipeline.py --source dataset   # Depuis le dataset local
    python pipeline.py --source minio     # Depuis MinIO
    python pipeline.py --scenario 5       # Traiter 5 scénarios
"""

import os
import sys
import json
import argparse
import tempfile
from datetime import datetime
from pathlib import Path

# Pour communiquer avec les services
import httpx

# Pour MinIO
try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    print("⚠️  MinIO non installé. Utiliser: pip install minio")

# Ajouter les chemins pour les imports locaux
sys.path.insert(0, str(Path(__file__).parent / "validation-service"))
sys.path.insert(0, str(Path(__file__).parent / "ocr-app"))
sys.path.insert(0, str(Path(__file__).parent / "ocr-app" / "app"))

# Importer l'extracteur de champs OCR
from field_extractor import extract_fields, guess_document_type

# ─────────────────────────────────────────────────────────────────────────────
# Configuration (utilise les variables d'environnement si disponibles)
# ─────────────────────────────────────────────────────────────────────────────

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_USER = os.environ.get("MINIO_USER", "minioadmin")
MINIO_PASSWORD = os.environ.get("MINIO_PASSWORD", "minioadmin")

VALIDATION_SERVICE_URL = os.environ.get("VALIDATION_SERVICE_URL", "http://localhost:8001")
OCR_SERVICE_URL = os.environ.get("OCR_SERVICE_URL", "http://localhost:8002")

DATASET_DIR = Path(os.environ.get("DATASET_DIR", str(Path(__file__).parent / "dataset" / "output")))
LABELS_DIR = DATASET_DIR / "labels"

# ─────────────────────────────────────────────────────────────────────────────
# Clients
# ─────────────────────────────────────────────────────────────────────────────

def get_minio_client():
    """Crée un client MinIO"""
    if not MINIO_AVAILABLE:
        return None
    try:
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_USER,
            secret_key=MINIO_PASSWORD,
            secure=False,
        )
        # Test de connexion
        client.list_buckets()
        return client
    except Exception as e:
        print(f"⚠️  MinIO non disponible: {e}")
        return None


def check_validation_service():
    """Vérifie si le service de validation est disponible"""
    try:
        r = httpx.get(f"{VALIDATION_SERVICE_URL}/health", timeout=5)
        return r.status_code == 200
    except:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# OCR Local (fallback si pas d'API OCR)
# ─────────────────────────────────────────────────────────────────────────────

def run_ocr_local(pdf_path: str) -> str:
    """Exécute l'OCR localement avec Tesseract"""
    try:
        from ocr_runner import extract_text_from_pdf
        return extract_text_from_pdf(Path(pdf_path))
    except ImportError:
        # Fallback: utiliser le module OCR directement
        try:
            sys.path.insert(0, str(Path(__file__).parent / "ocr-app" / "app"))
            from ocr_runner import extract_text_from_pdf
            return extract_text_from_pdf(Path(pdf_path))
        except Exception as e:
            print(f"    ⚠️ OCR non disponible: {e}")
            return ""


# ─────────────────────────────────────────────────────────────────────────────
# OCR Pipeline - Extraction réelle depuis PDFs
# ─────────────────────────────────────────────────────────────────────────────

def find_pdf_folders() -> list[Path]:
    """Trouve tous les dossiers de scénarios contenant des PDFs"""
    base_paths = [
        DATASET_DIR / "train" / "raw",
        DATASET_DIR / "test" / "raw",
    ]
    
    folders = []
    for base in base_paths:
        if base.exists():
            for folder in base.iterdir():
                if folder.is_dir() and any(folder.glob("*.pdf")):
                    folders.append(folder)
    
    return sorted(folders)


def process_folder_with_ocr(folder: Path, minio_client) -> tuple[dict, dict]:
    """
    Traite un dossier de scénario avec OCR réel.
    
    Returns:
        (validation_request, extracted_data) - requête pour validation et données extraites
    """
    scenario_id = folder.name
    extracted_data = {
        "scenario_id": scenario_id,
        "facture": None,
        "attestation_urssaf": None,
        "rib": None,
        "kbis": None,
        "devis": None,
        "raw_texts": {},
    }
    
    # Trouver tous les PDFs dans le dossier
    pdfs = list(folder.glob("*.pdf"))
    
    for pdf_path in pdfs:
        doc_name = pdf_path.stem.lower()
        
        # 1. OCR
        print(f"      🔍 OCR: {pdf_path.name}...")
        ocr_text = run_ocr_local(str(pdf_path))
        
        if not ocr_text:
            print(f"      ⚠️  OCR échoué pour {pdf_path.name}")
            continue
        
        # Sauvegarder le texte OCR dans MinIO (zone clean)
        save_to_minio_clean(minio_client, scenario_id, doc_name, ocr_text)
        
        # Stocker le texte brut
        extracted_data["raw_texts"][doc_name] = ocr_text
        
        # 2. Extraire les champs avec field_extractor
        fields_result = extract_fields(ocr_text, pdf_path.name)
        doc_type = fields_result.get("document_type_guess", "inconnu")
        fields = fields_result.get("fields", {})
        
        print(f"      📝 Type détecté: {doc_type}")
        
        # 3. Structurer selon le type de document
        if doc_type == "facture":
            extracted_data["facture"] = {
                "siret": fields.get("siret", {}).get("value"),
                "tva_intracom": fields.get("tva", {}).get("value"),
                "iban": fields.get("iban", {}).get("value"),
                "total_ht": fields.get("montant_ht", {}).get("value"),
                "montant_tva": fields.get("montant_tva", {}).get("value"),
                "total_ttc": fields.get("montant_ttc", {}).get("value"),
                "date_facture": fields.get("date_emission", {}).get("value"),
            }
        elif doc_type == "attestation":
            extracted_data["attestation_urssaf"] = {
                "siret": fields.get("siret", {}).get("value"),
                "date_debut_validite": fields.get("date_emission", {}).get("value"),
                "date_fin_validite": fields.get("date_expiration", {}).get("value"),
            }
        elif doc_type == "rib":
            extracted_data["rib"] = {
                "iban": fields.get("iban", {}).get("value"),
                "bic": fields.get("bic", {}).get("value"),
            }
        elif doc_type == "devis":
            extracted_data["devis"] = {
                "siret": fields.get("siret", {}).get("value"),
                "total_ht": fields.get("montant_ht", {}).get("value"),
                "total_ttc": fields.get("montant_ttc", {}).get("value"),
            }
    
    # Convertir en format validation
    validation_request = convert_extracted_to_validation_request(extracted_data)
    
    return validation_request, extracted_data


def convert_extracted_to_validation_request(data: dict) -> dict:
    """Convertit les données extraites vers le format attendu par validation-service"""
    from datetime import date
    
    request = {
        "dossier": {
            "dossier_id": data["scenario_id"],
        }
    }
    
    # Facture
    if data.get("facture"):
        f = data["facture"]
        request["dossier"]["facture"] = {
            "fichier_source": "facture.pdf",
            "numero_facture": "INCONNU",
            "siret_emetteur": f.get("siret") or "",
            "montant_ht": f.get("total_ht") or 0,
            "taux_tva": 0.20,
            "montant_tva": f.get("montant_tva") or 0,
            "montant_ttc": f.get("total_ttc") or 0,
            "date_emission": f.get("date_facture") or date.today().isoformat(),
            "iban": f.get("iban"),
        }
    
    # Attestation URSSAF
    if data.get("attestation_urssaf"):
        a = data["attestation_urssaf"]
        request["dossier"]["attestation_urssaf"] = {
            "fichier_source": "attestation_urssaf.pdf",
            "numero_attestation": "",
            "siret": a.get("siret") or "",
            "date_edition": a.get("date_debut_validite") or date.today().isoformat(),
            "date_expiration": a.get("date_fin_validite") or date.today().isoformat(),
        }
    
    # RIB
    if data.get("rib"):
        r = data["rib"]
        request["dossier"]["rib"] = {
            "fichier_source": "rib.pdf",
            "iban": r.get("iban") or "",
            "bic": r.get("bic") or "BNPAFRPP",
            "titulaire": "",
        }
    
    # Devis
    if data.get("devis"):
        d = data["devis"]
        request["dossier"]["devis"] = {
            "fichier_source": "devis.pdf",
            "numero_devis": "INCONNU",
            "siret_emetteur": d.get("siret") or "",
            "montant_ht": d.get("total_ht") or 0,
            "montant_ttc": d.get("total_ttc") or 0,
        }
    
    request["use_ml"] = False
    return request


def run_pipeline_with_ocr(folders: list[Path], minio_client):
    """Exécute le pipeline complet avec OCR réel"""
    
    stats = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "errors": 0,
        "ocr_success": 0,
        "saved_curated": 0,
        "anomalies_detected": 0,
    }
    
    for folder in folders:
        scenario_id = folder.name
        stats["total"] += 1
        
        print(f"\n{'─'*60}")
        print(f"📁 Dossier: {scenario_id}")
        
        # Étape 1: OCR + Parsing
        try:
            validation_request, extracted_data = process_folder_with_ocr(folder, minio_client)
            stats["ocr_success"] += 1
        except Exception as e:
            print(f"   ❌ Erreur OCR/Parsing: {e}")
            stats["errors"] += 1
            continue
        
        # Afficher les données extraites
        print(f"   📊 Données extraites:")
        if extracted_data.get("facture"):
            f = extracted_data["facture"]
            print(f"      Facture: HT={f.get('total_ht')}, TTC={f.get('total_ttc')}")
        if extracted_data.get("attestation_urssaf"):
            a = extracted_data["attestation_urssaf"]
            print(f"      Attestation: SIRET={a.get('siret')}, validité={a.get('date_fin_validite')}")
        if extracted_data.get("rib"):
            print(f"      RIB: IBAN={extracted_data['rib'].get('iban')}")
        
        # Étape 2: Validation
        print(f"   ✔️  Envoi au service de validation...")
        result = call_validation_service(validation_request)
        
        if result is None:
            stats["errors"] += 1
            continue
        
        # Étape 3: Analyser le résultat
        is_valid = result.get("est_valide", False)
        anomalies = result.get("anomalies", [])
        score = result.get("score_confiance", 0)
        
        if is_valid:
            stats["valid"] += 1
            status = "✅ VALIDE"
        else:
            stats["invalid"] += 1
            status = "❌ INVALIDE"
            stats["anomalies_detected"] += len(anomalies)
        
        print(f"   {status} (score: {score:.2f})")
        
        if anomalies:
            print(f"   📋 Anomalies détectées:")
            for a in anomalies[:3]:
                print(f"      • [{a.get('type_anomalie')}] {a.get('message', '')[:50]}")
        
        # Étape 4: Sauvegarder dans Curated
        full_result = {
            "scenario_id": scenario_id,
            "source": "ocr",
            "extracted_data": {
                "facture": extracted_data.get("facture"),
                "attestation": extracted_data.get("attestation_urssaf"),
                "rib": extracted_data.get("rib"),
            },
            "validation_result": result,
            "timestamp": datetime.now().isoformat(),
        }
        
        if save_to_minio_curated(minio_client, scenario_id, full_result):
            stats["saved_curated"] += 1
            print(f"   💾 Sauvegardé dans MinIO (curated)")
    
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Steps
# ─────────────────────────────────────────────────────────────────────────────

def load_dataset_labels() -> list:
    """Charge les labels du dataset le plus récent"""
    # Essayer plusieurs chemins possibles
    possible_paths = [
        LABELS_DIR,
        Path("/app/dataset/output/labels"),  # Docker
        Path(__file__).parent / "dataset" / "output" / "labels",
    ]
    
    labels_dir = None
    for p in possible_paths:
        if p.exists():
            labels_dir = p
            break
    
    if not labels_dir:
        print(f"❌ Dossier labels non trouvé")
        print(f"   Chemins essayés: {[str(p) for p in possible_paths]}")
        return []
    
    json_files = list(labels_dir.glob("dataset_*.json"))
    if not json_files:
        print(f"❌ Aucun fichier dataset trouvé dans {labels_dir}")
        return []
    
    latest = max(json_files, key=os.path.getmtime)
    print(f"📂 Dataset: {latest.name}")
    
    with open(latest, "r", encoding="utf-8") as f:
        return json.load(f)


def convert_scenario_to_validation_request(scenario: dict) -> dict:
    """Convertit un scénario du dataset en requête pour le service de validation"""
    from datetime import date
    
    dossier = {
        "dossier_id": scenario.get("scenario_id", "UNKNOWN"),
        "fournisseur_nom": scenario.get("fournisseur", {}).get("nom"),
    }
    
    documents = scenario.get("documents", [])
    fournisseur = scenario.get("fournisseur", {})
    
    # Récupérer l'IBAN réel pour détecter la fraude RIB
    iban_reel = None
    for doc in documents:
        if doc.get("type") == "rib":
            iban_reel = doc.get("iban_reel")
            break
    
    for doc in documents:
        doc_type = doc.get("type")
        anomalies = doc.get("anomalies", {})
        
        if doc_type == "facture":
            tva_affichee = anomalies.get("tva_displayed", doc.get("tva_amount_real", 0))
            dossier["facture"] = {
                "fichier_source": doc.get("fichier", ""),
                "numero_facture": doc.get("num_facture", ""),
                "siret_emetteur": doc.get("emetteur_siret", fournisseur.get("siret", "")),
                "siret_destinataire": doc.get("destinataire_siret"),
                "montant_ht": float(doc.get("total_ht", 0)),
                "taux_tva": float(doc.get("taux_tva", 0.20)),
                "montant_tva": float(tva_affichee),
                "montant_ttc": float(doc.get("total_ttc_displayed", doc.get("total_ttc_real", 0))),
                "date_emission": doc.get("date_emission", date.today().isoformat()),
                "date_echeance": doc.get("date_echeance"),
                "iban": iban_reel,
            }
        
        elif doc_type == "attestation_urssaf":
            dossier["attestation_urssaf"] = {
                "fichier_source": doc.get("fichier", ""),
                "numero_attestation": doc.get("num_attestation", ""),
                "siret": doc.get("siret_affiche", fournisseur.get("siret", "")),
                "date_edition": doc.get("date_edition", date.today().isoformat()),
                "date_expiration": doc.get("date_expiration", date.today().isoformat()),
                "raison_sociale": fournisseur.get("nom"),
            }
        
        elif doc_type == "rib":
            dossier["rib"] = {
                "fichier_source": doc.get("fichier", ""),
                "iban": doc.get("iban_affiche", doc.get("iban_reel", "")),
                "bic": doc.get("bic", "BNPAFRPP"),
                "titulaire": fournisseur.get("nom", ""),
                "siret": fournisseur.get("siret"),
            }
        
        elif doc_type == "kbis":
            siret = fournisseur.get("siret", "")
            dossier["kbis"] = {
                "fichier_source": doc.get("fichier", ""),
                "siren": siret[:9] if len(siret) >= 9 else siret,
                "siret_siege": siret,
                "raison_sociale": fournisseur.get("nom", ""),
                "forme_juridique": doc.get("forme_juridique", "SARL"),
                "date_extrait": doc.get("date_extrait", date.today().isoformat()),
            }
        
        elif doc_type == "devis":
            dossier["devis"] = {
                "fichier_source": doc.get("fichier", ""),
                "numero_devis": doc.get("num_devis", ""),
                "siret_emetteur": doc.get("emetteur_siret", fournisseur.get("siret", "")),
                "montant_ht": float(doc.get("total_ht", 0)),
                "taux_tva": float(doc.get("taux_tva", 0.20)),
                "montant_tva": float(doc.get("tva_amount", 0)),
                "montant_ttc": float(doc.get("total_ttc", 0)),
                "date_emission": doc.get("date_emission", date.today().isoformat()),
            }
    
    return {"dossier": dossier, "use_ml": False}


def call_validation_service(request: dict) -> dict:
    """Appelle le service de validation via HTTP"""
    try:
        response = httpx.post(
            f"{VALIDATION_SERVICE_URL}/validate",
            json=request,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        print("    ❌ Service de validation non disponible")
        print("       Lancez: cd validation-service && uvicorn app.main:app --port 8001")
        return None
    except Exception as e:
        print(f"    ❌ Erreur validation: {e}")
        return None


def save_to_minio_curated(client, scenario_id: str, result: dict):
    """Sauvegarde le résultat dans la zone Curated de MinIO"""
    if not client:
        return False
    
    try:
        # Créer le bucket si nécessaire
        if not client.bucket_exists("curated"):
            client.make_bucket("curated")
        
        # Sauvegarder le résultat
        today = datetime.today().strftime("%Y-%m-%d")
        object_name = f"{today}/validated/{scenario_id}.json"
        
        import io
        data = json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8")
        client.put_object(
            "curated",
            object_name,
            io.BytesIO(data),
            len(data),
            content_type="application/json",
        )
        return True
    except Exception as e:
        print(f"    ⚠️ Erreur MinIO: {e}")
        return False


def save_to_minio_clean(client, scenario_id: str, doc_name: str, ocr_text: str):
    """Sauvegarde le texte OCR dans la zone Clean de MinIO"""
    if not client or not ocr_text:
        return False
    
    try:
        if not client.bucket_exists("clean"):
            client.make_bucket("clean")
        
        today = datetime.today().strftime("%Y-%m-%d")
        object_name = f"{today}/{scenario_id}/{doc_name}.txt"
        
        import io
        data = ocr_text.encode("utf-8")
        client.put_object(
            "clean",
            object_name,
            io.BytesIO(data),
            len(data),
            content_type="text/plain",
        )
        return True
    except Exception as e:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Main Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(scenarios: list, minio_client, use_ocr: bool = False):
    """Exécute le pipeline complet sur une liste de scénarios"""
    
    stats = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "errors": 0,
        "saved_curated": 0,
        "anomalies_detected": 0,
    }
    
    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "unknown")
        scenario_type = scenario.get("scenario_type", "unknown")
        expected_anomalies = scenario.get("anomalies_attendues", [])
        
        stats["total"] += 1
        print(f"\n{'─'*60}")
        print(f"📄 {scenario_id}")
        print(f"   Type: {scenario_type}")
        print(f"   Anomalies attendues: {expected_anomalies or 'aucune'}")
        
        # Étape 1: OCR (optionnel)
        if use_ocr:
            for doc in scenario.get("documents", []):
                pdf_path = doc.get("fichier")
                if pdf_path and Path(pdf_path).exists():
                    print(f"   🔍 OCR: {Path(pdf_path).name}...")
                    ocr_text = run_ocr_local(pdf_path)
                    if ocr_text:
                        save_to_minio_clean(minio_client, scenario_id, Path(pdf_path).stem, ocr_text)
        
        # Étape 2: Validation
        print(f"   ✔️  Validation...")
        request = convert_scenario_to_validation_request(scenario)
        result = call_validation_service(request)
        
        if result is None:
            stats["errors"] += 1
            continue
        
        # Étape 3: Analyser le résultat
        is_valid = result.get("est_valide", False)
        anomalies = result.get("anomalies", [])
        score = result.get("score_confiance", 0)
        
        if is_valid:
            stats["valid"] += 1
            status = "✅ VALIDE"
        else:
            stats["invalid"] += 1
            status = "❌ INVALIDE"
            stats["anomalies_detected"] += len(anomalies)
        
        print(f"   {status} (score: {score:.2f})")
        
        if anomalies:
            print(f"   📋 Anomalies détectées:")
            for a in anomalies[:3]:  # Max 3 pour lisibilité
                print(f"      • [{a.get('type_anomalie')}] {a.get('message', '')[:50]}")
        
        # Étape 4: Sauvegarder dans Curated
        full_result = {
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "anomalies_attendues": expected_anomalies,
            "validation_result": result,
            "timestamp": datetime.now().isoformat(),
        }
        
        if save_to_minio_curated(minio_client, scenario_id, full_result):
            stats["saved_curated"] += 1
            print(f"   💾 Sauvegardé dans MinIO (curated)")
    
    return stats


def print_summary(stats: dict):
    """Affiche le résumé du pipeline"""
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DU PIPELINE")
    print("=" * 60)
    print(f"   Scénarios traités:     {stats['total']}")
    print(f"   ✅ Valides:            {stats['valid']}")
    print(f"   ❌ Invalides:          {stats['invalid']}")
    print(f"   ⚠️  Erreurs:            {stats['errors']}")
    print(f"   🔍 Anomalies détectées: {stats['anomalies_detected']}")
    if stats['saved_curated'] > 0:
        print(f"   💾 Sauvés dans MinIO:  {stats['saved_curated']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Pipeline d'intégration")
    parser.add_argument("--source", choices=["dataset", "minio"], default="dataset",
                        help="Source des données (default: dataset)")
    parser.add_argument("--scenario", "-n", type=int, default=10,
                        help="Nombre de scénarios à traiter (default: 10)")
    parser.add_argument("--ocr", action="store_true",
                        help="Exécuter l'OCR sur les PDFs (sauvegarde texte uniquement)")
    parser.add_argument("--real-ocr", action="store_true",
                        help="🆕 Pipeline complet: OCR → Parser → Validation (sans utiliser les labels)")
    parser.add_argument("--all", action="store_true",
                        help="Traiter tous les scénarios")
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("   🔄 PIPELINE D'INTÉGRATION - HACKATHON 2026")
    print("=" * 60)
    
    # Mode OCR réel
    if args.real_ocr:
        print("\n📡 Mode: OCR RÉEL (PDF → OCR → Parser → Validation)")
        print("   Ce mode extrait les données RÉELLEMENT depuis les PDFs")
        
        # Vérifier le service de validation
        if not check_validation_service():
            print("\n   ❌ Service de validation non disponible")
            print("   👉 Lancez: cd validation-service && uvicorn app.main:app --port 8001")
            return
        print("   ✅ Service de validation OK")
        
        # Vérifier l'OCR
        try:
            from ocr_runner import extract_text_from_pdf
            print("   ✅ Module OCR disponible")
        except ImportError as e:
            print(f"   ❌ Module OCR non disponible: {e}")
            print("   👉 Installez: pip install pytesseract pdf2image pillow")
            print("   👉 Installez Tesseract: https://github.com/tesseract-ocr/tesseract")
            return
        
        minio_client = get_minio_client()
        if minio_client:
            print("   ✅ MinIO connecté")
        else:
            print("   ⚠️  MinIO non disponible")
        
        # Trouver les dossiers PDF
        folders = find_pdf_folders()
        if not folders:
            print("\n❌ Aucun dossier PDF trouvé")
            print("   👉 Générez le dataset: cd dataset && python generate_dataset.py")
            return
        
        if not args.all:
            folders = folders[:args.scenario]
        
        print(f"\n📂 {len(folders)} dossiers à traiter")
        
        # Exécuter le pipeline OCR
        stats = run_pipeline_with_ocr(folders, minio_client)
        
        # Résumé
        print("\n" + "=" * 60)
        print("📊 RÉSUMÉ DU PIPELINE (OCR RÉEL)")
        print("=" * 60)
        print(f"   Dossiers traités:      {stats['total']}")
        print(f"   OCR réussis:           {stats['ocr_success']}")
        print(f"   ✅ Valides:            {stats['valid']}")
        print(f"   ❌ Invalides:          {stats['invalid']}")
        print(f"   ⚠️  Erreurs:            {stats['errors']}")
        print(f"   🔍 Anomalies détectées: {stats['anomalies_detected']}")
        if stats['saved_curated'] > 0:
            print(f"   💾 Sauvés dans MinIO:  {stats['saved_curated']}")
        print("=" * 60)
        return
    
    # ─────────────────────────────────────────────────────────────────
    # Mode standard (utilise les labels JSON)
    # ─────────────────────────────────────────────────────────────────
    print("\n📡 Mode: LABELS (utilise les labels JSON comme ground truth)")
    
    # Vérifier les services
    print("\n📡 Vérification des services...")
    
    minio_client = get_minio_client()
    if minio_client:
        print("   ✅ MinIO connecté")
    else:
        print("   ⚠️  MinIO non disponible (résultats non sauvegardés)")
    
    if check_validation_service():
        print("   ✅ Service de validation OK")
    else:
        print("   ❌ Service de validation non disponible")
        print("\n   👉 Lancez le service avec:")
        print("      cd validation-service")
        print("      pip install -r requirements.txt")
        print("      uvicorn app.main:app --port 8001")
        return
    
    # Charger les données
    print(f"\n📥 Chargement des données ({args.source})...")
    
    if args.source == "dataset":
        scenarios = load_dataset_labels()
    else:
        # TODO: Charger depuis MinIO
        print("   ⚠️  Chargement depuis MinIO non implémenté")
        scenarios = load_dataset_labels()
    
    if not scenarios:
        print("❌ Aucun scénario trouvé")
        print("\n   👉 Générez le dataset avec:")
        print("      cd dataset")
        print("      python generate_dataset.py --n_train 20 --n_test 5")
        return
    
    # Limiter le nombre de scénarios
    if not args.all:
        scenarios = scenarios[:args.scenario]
    
    print(f"   {len(scenarios)} scénarios à traiter")
    
    # Exécuter le pipeline
    stats = run_pipeline(scenarios, minio_client, use_ocr=args.ocr)
    
    # Résumé
    print_summary(stats)


if __name__ == "__main__":
    main()
