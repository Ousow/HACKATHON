"""
Script principal de génération du dataset.
Usage : python generate_dataset.py [--n_train 200] [--n_test 50] [--degrade]
"""
import os
import json
import argparse
import random
from tqdm import tqdm
from datetime import datetime

# Chemin racine du projet
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")

from scenarios.scenario_builder import SCENARIOS, build_scenario

# Distribution des scénarios (pondérée) : légitimes ~55%, anomalies ~45%
SCENARIO_WEIGHTS = {
    "legitime_complet": 30,
    "legitime_minimal": 20,
    "siret_incoherent_facture_attestation": 12,
    "tva_incoherente": 8,
    "montant_falsifie": 8,
    "attestation_expiree": 12,
    "rib_incoherent": 8,
    "facture_sans_justificatif": 6,
    "tva_et_montant_falsifies": 4,
    "multi_anomalies": 8,
}
_scenario_pool = [k for k, w in SCENARIO_WEIGHTS.items() for _ in range(w)]


def apply_degradation_to_scenario(scenario_dir: str, split: str) -> list[dict]:
    """
    Convertit les PDF d'un scénario en images dégradées.
    Utilise PyMuPDF (fitz) — aucune dépendance externe (pas de Poppler).
    """
    import fitz  # PyMuPDF
    from PIL import Image
    from degradation.image_degrader import degrade_image, DEGRADATION_PROFILES

    degraded_records = []
    raw_dir = scenario_dir

    for pdf_file in os.listdir(raw_dir):
        if not pdf_file.endswith(".pdf"):
            continue
        pdf_path = os.path.join(raw_dir, pdf_file)

        # Déterminer le dossier dégradé correspondant
        degraded_dir = raw_dir.replace(
            os.path.join("output", split, "raw"),
            os.path.join("output", split, "degraded")
        )
        os.makedirs(degraded_dir, exist_ok=True)

        try:
            pdf_doc = fitz.open(pdf_path)
        except Exception as e:
            print(f"  [WARN] PyMuPDF ne peut pas ouvrir {pdf_file}: {e}")
            continue

        mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
        for i, page in enumerate(pdf_doc):
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            profile = random.choice([k for k in DEGRADATION_PROFILES.keys() if k != "clean"])
            degraded_img, used_profile = degrade_image(img, profile)
            out_name = pdf_file.replace(".pdf", f"_p{i+1}_{used_profile}.jpg")
            out_path = os.path.join(degraded_dir, out_name)
            degraded_img.save(out_path, "JPEG", quality=random.randint(55, 90))
            degraded_records.append({
                "source_pdf": pdf_path,
                "degraded_image": out_path,
                "degradation_profile": used_profile,
            })

        pdf_doc.close()

    return degraded_records


def generate_dataset(n_train: int, n_test: int, degrade: bool):
    """Génère l'ensemble du dataset."""
    os.makedirs(LABELS_DIR, exist_ok=True)

    all_records = []
    total = n_train + n_test

    print(f"\n{'='*60}")
    print(f"  Génération du dataset Hackathon 2026")
    print(f"  Train: {n_train} | Test: {n_test} | Dégradation: {degrade}")
    print(f"{'='*60}\n")

    scenario_counter = 0

    for split, count in [("train", n_train), ("test", n_test)]:
        print(f"--- Split : {split} ({count} scénarios) ---")
        for i in tqdm(range(count), desc=split):
            scenario_name = random.choice(_scenario_pool)
            try:
                result = build_scenario(
                    scenario_name=scenario_name,
                    output_dir=OUTPUT_DIR,
                    scenario_id=scenario_counter,
                    split=split,
                )

                if degrade:
                    scenario_dir = os.path.join(
                        OUTPUT_DIR, split, "raw",
                        f"{scenario_name}_{scenario_counter:04d}"
                    )
                    degraded = apply_degradation_to_scenario(scenario_dir, split)
                    result["degraded_images"] = degraded

                all_records.append(result)
                scenario_counter += 1

            except Exception as e:
                print(f"\n  [ERROR] Scénario {scenario_name} #{scenario_counter}: {e}")
                scenario_counter += 1
                continue

    # Sauvegarde des labels
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    labels_path = os.path.join(LABELS_DIR, f"dataset_{ts}.json")
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    # Résumé CSV
    import pandas as pd
    rows = []
    for r in all_records:
        rows.append({
            "scenario_id": r["scenario_id"],
            "scenario_type": r["scenario_type"],
            "split": r["split"],
            "has_anomaly": len(r["anomalies_attendues"]) > 0,
            "anomalies": ", ".join(r["anomalies_attendues"]) if r["anomalies_attendues"] else "none",
            "fournisseur_siret": r["fournisseur"]["siret"],
            "n_documents": len(r["documents"]),
        })
    df = pd.DataFrame(rows)
    csv_path = os.path.join(LABELS_DIR, f"dataset_{ts}.csv")
    df.to_csv(csv_path, index=False)

    # Stats
    print(f"\n{'='*60}")
    print(f"  Dataset généré avec succès !")
    print(f"  Labels JSON : {labels_path}")
    print(f"  Labels CSV  : {csv_path}")
    print(f"  Scénarios   : {len(all_records)}")
    print(f"\n  Distribution des types :")
    print(df["scenario_type"].value_counts().to_string())
    print(f"\n  Légitimes : {(~df['has_anomaly']).sum()} | Avec anomalies : {df['has_anomaly'].sum()}")
    print(f"{'='*60}\n")

    return all_records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Générateur de dataset Hackathon 2026")
    parser.add_argument("--n_train", type=int, default=200, help="Nb scénarios train (défaut: 200)")
    parser.add_argument("--n_test", type=int, default=50, help="Nb scénarios test (défaut: 50)")
    parser.add_argument("--degrade", action="store_true", help="Générer aussi les images dégradées")
    args = parser.parse_args()

    generate_dataset(
        n_train=args.n_train,
        n_test=args.n_test,
        degrade=args.degrade,
    )
