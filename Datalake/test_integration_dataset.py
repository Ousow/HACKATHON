"""
Test d'intégration : alimente le Data Lake MinIO avec le dataset hackathon.

Ce script :
  1. Upload les PDFs bruts (train + test) → Raw zone
  2. Upload les fichiers labels JSON        → Curated zone
  3. Affiche un rapport complet

Usage :
    python test_integration_dataset.py               # teste 5 scénarios par défaut
    python test_integration_dataset.py --all         # charge TOUT le dataset
    python test_integration_dataset.py --split test  # seulement le split test
    python test_integration_dataset.py --n 20        # 20 scénarios aléatoires
"""

import os
import sys
import json
import io
import argparse
import random
from datetime import datetime
from pathlib import Path
from minio import Minio
from minio.error import S3Error

# ── Configuration ──────────────────────────────────────────────────────────────
MINIO_ENDPOINT  = "localhost:9000"
MINIO_USER      = "minioadmin"
MINIO_PASSWORD  = "minioadmin"

DATASET_DIR = Path(r"C:\Users\oumis\Desktop\HACKATHON\dataset\output")
LABELS_DIR  = DATASET_DIR / "labels"

TODAY = datetime.today().strftime("%Y-%m-%d")

# ── Client MinIO ───────────────────────────────────────────────────────────────
client = Minio(MINIO_ENDPOINT, access_key=MINIO_USER, secret_key=MINIO_PASSWORD, secure=False)

# ── Couleurs terminal (Windows compatible) ─────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET}  {msg}")
def err(msg):   print(f"  {RED}✗{RESET}  {msg}")
def info(msg):  print(f"  {BLUE}→{RESET}  {msg}")
def sep():      print(f"  {'─' * 60}")


# ── Étape 1 : Upload PDFs bruts → Raw ─────────────────────────────────────────
def upload_scenarios_to_raw(scenario_dirs: list[Path], split: str) -> dict:
    """Upload tous les PDFs d'une liste de dossiers scénario dans raw/<split>/."""
    stats = {"uploaded": 0, "skipped": 0, "errors": 0, "bytes": 0}
    for scenario_dir in scenario_dirs:
        scenario_name = scenario_dir.name
        pdfs = list(scenario_dir.glob("*.pdf"))
        if not pdfs:
            continue
        for pdf_path in pdfs:
            obj_name = f"{TODAY}/{split}/{scenario_name}/{pdf_path.name}"
            try:
                client.fput_object("raw", obj_name, str(pdf_path))
                stats["uploaded"] += 1
                stats["bytes"]    += pdf_path.stat().st_size
                ok(f"raw/{obj_name.split('/', 1)[1]}  ({pdf_path.stat().st_size} B)")
            except S3Error as e:
                err(f"Erreur upload {pdf_path.name}: {e}")
                stats["errors"] += 1
    return stats


# ── Étape 2 : Upload labels JSON → Curated ───────────────────────────────────
def upload_labels_to_curated() -> dict:
    """Upload tous les fichiers JSON de labels dans curated/labels/."""
    stats = {"uploaded": 0, "errors": 0, "bytes": 0}
    json_files = sorted(LABELS_DIR.glob("*.json"))
    if not json_files:
        err("Aucun fichier JSON trouvé dans output/labels/")
        return stats

    for json_path in json_files:
        obj_name = f"{TODAY}/labels/{json_path.name}"
        try:
            client.fput_object("curated", obj_name, str(json_path))
            stats["uploaded"] += 1
            stats["bytes"]    += json_path.stat().st_size
            ok(f"curated/{obj_name.split('/', 1)[1]}  ({json_path.stat().st_size} B)")
        except S3Error as e:
            err(f"Erreur upload {json_path.name}: {e}")
            stats["errors"] += 1
    return stats


# ── Étape 3 : Créer un index JSON → Curated ──────────────────────────────────
def push_scenario_index(scenario_dirs_by_split: dict) -> None:
    """Crée un fichier index JSON listant tous les scénarios uploadés."""
    index = {
        "generated_at": datetime.now().isoformat(),
        "dataset_root":  str(DATASET_DIR),
        "splits": {}
    }
    for split, dirs in scenario_dirs_by_split.items():
        entries = []
        for d in dirs:
            pdfs = [p.name for p in d.glob("*.pdf")]
            entries.append({
                "scenario_id":   d.name,
                "scenario_type": "_".join(d.name.split("_")[:-1]),
                "split":         split,
                "documents":     pdfs,
                "raw_path":      f"{TODAY}/{split}/{d.name}/"
            })
        index["splits"][split] = entries

    content      = json.dumps(index, ensure_ascii=False, indent=2).encode("utf-8")
    obj_name     = f"{TODAY}/scenario_index.json"
    client.put_object("curated", obj_name, io.BytesIO(content),
                      length=len(content), content_type="application/json")
    ok(f"curated/{obj_name}  (index : {len(content)} B)")


# ── Étape 4 : Vérification finale ─────────────────────────────────────────────
def verify_buckets() -> None:
    """Compte les objets dans chaque bucket et affiche un résumé."""
    for bucket in ["raw", "clean", "curated"]:
        objects = list(client.list_objects(bucket, recursive=True))
        total_bytes = sum(o.size for o in objects)
        print(f"  {BOLD}{bucket:<10}{RESET} {len(objects):>5} objets   {total_bytes / 1024:>8.1f} KB")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Test intégration Dataset → MinIO Data Lake")
    parser.add_argument("--all",   action="store_true", help="Charge TOUT le dataset")
    parser.add_argument("--split", choices=["train", "test", "both"], default="both",
                        help="Split à charger (défaut: both)")
    parser.add_argument("--n",     type=int, default=5,
                        help="Nombre de scénarios par split si pas --all (défaut: 5)")
    args = parser.parse_args()

    print(f"\n{BOLD}══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}   TEST INTÉGRATION DATASET → DATA LAKE MINIO{RESET}")
    print(f"{BOLD}══════════════════════════════════════════════════════════════{RESET}\n")

    # Sélection des splits
    splits_to_process = []
    if args.split in ("train", "both"):
        splits_to_process.append("train")
    if args.split in ("test", "both"):
        splits_to_process.append("test")

    scenario_dirs_by_split = {}
    for split in splits_to_process:
        raw_dir = DATASET_DIR / split / "raw"
        if not raw_dir.exists():
            err(f"Dossier introuvable : {raw_dir}")
            continue
        all_dirs = [d for d in sorted(raw_dir.iterdir()) if d.is_dir()]
        if args.all:
            selected = all_dirs
        else:
            selected = random.sample(all_dirs, min(args.n, len(all_dirs)))
        scenario_dirs_by_split[split] = selected

    # ── Étape 1 : Raw ──────────────────────────────────────────────────────
    print(f"{BOLD}[1/4] Upload PDFs → Raw zone{RESET}")
    sep()
    total_raw = {"uploaded": 0, "errors": 0, "bytes": 0}
    for split, dirs in scenario_dirs_by_split.items():
        info(f"Split {split.upper()} : {len(dirs)} scénario(s)")
        stats = upload_scenarios_to_raw(dirs, split)
        for k in total_raw:
            total_raw[k] += stats.get(k, 0)
    sep()
    print(f"  {GREEN}→ {total_raw['uploaded']} PDF(s) uploadés  "
          f"({total_raw['bytes']/1024:.1f} KB)  "
          f"{'  ' + RED + str(total_raw['errors']) + ' erreur(s)' + RESET if total_raw['errors'] else GREEN + '0 erreur' + RESET}\n")

    # ── Étape 2 : Curated – labels ─────────────────────────────────────────
    print(f"{BOLD}[2/4] Upload JSON labels → Curated zone{RESET}")
    sep()
    label_stats = upload_labels_to_curated()
    sep()
    print(f"  {GREEN}→ {label_stats['uploaded']} fichier(s) JSON uploadés  "
          f"({label_stats['bytes']/1024:.1f} KB)\n")

    # ── Étape 3 : Index ────────────────────────────────────────────────────
    print(f"{BOLD}[3/4] Génération de l'index des scénarios → Curated zone{RESET}")
    sep()
    push_scenario_index(scenario_dirs_by_split)
    sep()
    print()

    # ── Étape 4 : Vérification ─────────────────────────────────────────────
    print(f"{BOLD}[4/4] État final des buckets MinIO{RESET}")
    sep()
    verify_buckets()
    sep()

    print(f"\n{GREEN}{BOLD}  ✓ Intégration terminée avec succès !{RESET}")
    print(f"  Interface MinIO : http://localhost:9001  (minioadmin / minioadmin)\n")


if __name__ == "__main__":
    main()
