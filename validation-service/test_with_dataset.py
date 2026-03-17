"""
Script d'intégration : Valide les données du dataset réel.

Ce script :
1. Lit les labels JSON générés par le dataset
2. Convertit chaque scénario en DossierFournisseur
3. Exécute la validation
4. Compare les anomalies détectées aux anomalies attendues

Usage:
  1. D'abord générer le dataset :
     cd ../dataset
     python generate_dataset.py --n_train 50 --n_test 10
  
  2. Puis lancer ce script :
     cd ../validation-service
     python test_with_dataset.py
"""

import os
import sys
import json
from datetime import date, datetime
from pathlib import Path

# Ajouter le chemin pour les imports
sys.path.insert(0, '.')

from app.models.schemas import (
    DossierFournisseur,
    FactureExtrait,
    AttestationURSSAFExtrait,
    DevisExtrait,
    KbisExtrait,
    RIBExtrait,
    TypeAnomalie,
)
from app.services.validation_engine import ValidationEngine


# Mapping entre les anomalies du dataset et les types d'anomalies du validateur
ANOMALY_MAPPING = {
    "siret_incoherent": TypeAnomalie.SIRET_INCOHERENT,
    "tva_incoherente": TypeAnomalie.TVA_INCOHERENTE,
    "montant_falsifie": TypeAnomalie.MONTANT_FALSIFIE,
    "attestation_expiree": TypeAnomalie.ATTESTATION_EXPIREE,
    "rib_incoherent": TypeAnomalie.RIB_INCOHERENT,
    "document_manquant": TypeAnomalie.DOCUMENT_MANQUANT,
}


def find_latest_dataset():
    """Trouve le fichier JSON de dataset le plus récent"""
    labels_dir = Path(__file__).parent.parent / "dataset" / "output" / "labels"
    
    if not labels_dir.exists():
        print(f"❌ Dossier labels non trouvé: {labels_dir}")
        print("   Génère d'abord le dataset avec:")
        print("   cd ../dataset && python generate_dataset.py")
        return None
    
    json_files = list(labels_dir.glob("dataset_*.json"))
    
    if not json_files:
        print(f"❌ Aucun fichier dataset trouvé dans {labels_dir}")
        return None
    
    # Prendre le plus récent
    latest = max(json_files, key=os.path.getmtime)
    return latest


def parse_date(date_str: str) -> date:
    """Parse une date depuis différents formats"""
    if isinstance(date_str, date):
        return date_str
    
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return date.today()


def convert_to_dossier(scenario: dict) -> DossierFournisseur:
    """
    Convertit un scénario du dataset en DossierFournisseur.
    
    Les champs du dataset sont :
    - Facture: num_facture, total_ht, taux_tva, tva_amount_real, total_ttc_displayed, emetteur_siret
    - Attestation: num_attestation, siret_affiche, date_edition, date_expiration
    - RIB: iban_affiche, iban_reel, bic
    
    Args:
        scenario: dict du scénario (depuis le JSON)
        
    Returns:
        DossierFournisseur prêt pour la validation
    """
    dossier_id = scenario.get("scenario_id", "UNKNOWN")
    fournisseur = scenario.get("fournisseur", {})
    documents = scenario.get("documents", [])
    
    # Initialiser le dossier
    dossier = DossierFournisseur(
        dossier_id=dossier_id,
        fournisseur_nom=fournisseur.get("nom"),
    )
    
    # Parser chaque document
    # D'abord, récupérer l'IBAN réel du fournisseur s'il existe dans un RIB
    iban_fournisseur_reel = None
    for doc in documents:
        if doc.get("type") == "rib":
            iban_fournisseur_reel = doc.get("iban_reel")
            break
    
    for doc in documents:
        doc_type = doc.get("type")
        anomalies = doc.get("anomalies", {})
        
        if doc_type == "facture":
            # Récupérer la TVA affichée (peut être falsifiée)
            tva_affichee = anomalies.get("tva_displayed", doc.get("tva_amount_real", 0))
            
            dossier.facture = FactureExtrait(
                fichier_source=doc.get("fichier", ""),
                numero_facture=doc.get("num_facture", ""),
                siret_emetteur=doc.get("emetteur_siret", fournisseur.get("siret", "")),
                siret_destinataire=doc.get("destinataire_siret"),
                tva_intracommunautaire=doc.get("emetteur_tva"),
                montant_ht=float(doc.get("total_ht", 0)),
                taux_tva=float(doc.get("taux_tva", 0.20)),
                montant_tva=float(tva_affichee),
                montant_ttc=float(doc.get("total_ttc_displayed", doc.get("total_ttc_real", 0))),
                date_emission=parse_date(doc.get("date_emission", date.today().isoformat())),
                date_echeance=parse_date(doc.get("date_echeance")) if doc.get("date_echeance") else None,
                iban=iban_fournisseur_reel,  # IBAN réel du fournisseur pour comparaison avec le RIB
            )
        
        elif doc_type == "attestation_urssaf":
            dossier.attestation_urssaf = AttestationURSSAFExtrait(
                fichier_source=doc.get("fichier", ""),
                numero_attestation=doc.get("num_attestation", ""),
                siret=doc.get("siret_affiche", fournisseur.get("siret", "")),
                date_edition=parse_date(doc.get("date_edition", date.today().isoformat())),
                date_expiration=parse_date(doc.get("date_expiration", date.today().isoformat())),
                raison_sociale=fournisseur.get("nom"),
            )
        
        elif doc_type == "devis":
            dossier.devis = DevisExtrait(
                fichier_source=doc.get("fichier", ""),
                numero_devis=doc.get("num_devis", ""),
                siret_emetteur=doc.get("emetteur_siret", fournisseur.get("siret", "")),
                montant_ht=float(doc.get("total_ht", 0)),
                taux_tva=float(doc.get("taux_tva", 0.20)),
                montant_tva=float(doc.get("tva_amount", 0)),
                montant_ttc=float(doc.get("total_ttc", 0)),
                date_emission=parse_date(doc.get("date_emission", date.today().isoformat())),
            )
        
        elif doc_type == "kbis":
            siret = fournisseur.get("siret", "")
            dossier.kbis = KbisExtrait(
                fichier_source=doc.get("fichier", ""),
                siren=siret[:9] if len(siret) >= 9 else siret,
                siret_siege=siret,
                raison_sociale=fournisseur.get("nom", ""),
                forme_juridique=doc.get("forme_juridique", "SARL"),
                date_extrait=parse_date(doc.get("date_extrait", date.today().isoformat())),
            )
        
        elif doc_type == "rib":
            dossier.rib = RIBExtrait(
                fichier_source=doc.get("fichier", ""),
                iban=doc.get("iban_affiche", doc.get("iban_reel", "")),
                bic=doc.get("bic", "BNPAFRPP"),
                titulaire=fournisseur.get("nom", ""),
                siret=fournisseur.get("siret"),
            )
    
    return dossier


def check_detection(anomalies_attendues: list, anomalies_detectees: list) -> dict:
    """
    Compare les anomalies attendues aux anomalies détectées.
    
    Returns:
        dict avec les métriques de détection
    """
    # Convertir les anomalies attendues en types
    expected_types = set()
    for a in anomalies_attendues:
        if a in ANOMALY_MAPPING:
            expected_types.add(ANOMALY_MAPPING[a])
    
    # Types détectés (critiques et erreurs seulement)
    detected_types = set()
    for a in anomalies_detectees:
        if a.gravite in ["critical", "error"]:
            detected_types.add(TypeAnomalie(a.type_anomalie))
    
    # Calcul des métriques
    true_positives = expected_types & detected_types
    false_negatives = expected_types - detected_types
    false_positives = detected_types - expected_types
    
    return {
        "expected": expected_types,
        "detected": detected_types,
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
        "precision": len(true_positives) / len(detected_types) if detected_types else 1.0,
        "recall": len(true_positives) / len(expected_types) if expected_types else 1.0,
    }


def main():
    print("\n" + "=" * 70)
    print("   🔍 VALIDATION DU DATASET RÉEL")
    print("   Test d'intégration - Module Étudiant 5")
    print("=" * 70)
    
    # Trouver le dataset
    dataset_path = find_latest_dataset()
    if not dataset_path:
        return
    
    print(f"\n📂 Dataset trouvé: {dataset_path.name}")
    
    # Charger le dataset
    with open(dataset_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    
    print(f"   {len(scenarios)} scénarios à valider\n")
    
    # Initialiser le moteur
    engine = ValidationEngine(use_ml=False)
    
    # Statistiques
    stats = {
        "total": 0,
        "legitimes_ok": 0,
        "anomalies_detectees": 0,
        "true_positives": 0,
        "false_negatives": 0,
        "false_positives": 0,
    }
    
    # Valider chaque scénario
    print("-" * 70)
    
    for i, scenario in enumerate(scenarios[:20]):  # Limiter à 20 pour la démo
        scenario_id = scenario.get("scenario_id", f"scenario_{i}")
        scenario_type = scenario.get("scenario_type", "unknown")
        anomalies_attendues = scenario.get("anomalies_attendues", [])
        
        # Convertir et valider
        try:
            dossier = convert_to_dossier(scenario)
            result = engine.validate(dossier)
            
            # Analyser les résultats
            check = check_detection(anomalies_attendues, result.anomalies)
            
            # Afficher le résultat
            if not anomalies_attendues:
                # Scénario légitime
                status = "✅" if result.est_valide else "⚠️"
                if result.est_valide:
                    stats["legitimes_ok"] += 1
            else:
                # Scénario avec anomalies
                if check["recall"] == 1.0:
                    status = "✅"
                    stats["anomalies_detectees"] += 1
                elif check["recall"] > 0:
                    status = "🟡"
                else:
                    status = "❌"
            
            stats["total"] += 1
            stats["true_positives"] += len(check["true_positives"])
            stats["false_negatives"] += len(check["false_negatives"])
            stats["false_positives"] += len(check["false_positives"])
            
            # Affichage compact
            expected_str = ", ".join(anomalies_attendues) if anomalies_attendues else "légitime"
            detected_str = ", ".join([a.type_anomalie for a in result.anomalies if a.gravite in ["critical", "error"]]) or "aucune"
            
            print(f"{status} {scenario_id[:30]:<32} | Attendu: {expected_str[:25]:<25} | Détecté: {detected_str[:25]}")
            
        except Exception as e:
            print(f"❌ {scenario_id}: Erreur - {e}")
    
    # Résumé
    print("-" * 70)
    print("\n📊 RÉSUMÉ DE VALIDATION")
    print("-" * 40)
    print(f"  Scénarios traités:     {stats['total']}")
    print(f"  Légitimes validés:     {stats['legitimes_ok']}")
    print(f"  Anomalies détectées:   {stats['anomalies_detectees']}")
    print(f"  True Positives:        {stats['true_positives']}")
    print(f"  False Negatives:       {stats['false_negatives']}")
    print(f"  False Positives:       {stats['false_positives']}")
    
    # Métriques globales
    if stats["true_positives"] + stats["false_negatives"] > 0:
        recall = stats["true_positives"] / (stats["true_positives"] + stats["false_negatives"])
        print(f"\n  📈 Recall (détection): {recall:.1%}")
    
    if stats["true_positives"] + stats["false_positives"] > 0:
        precision = stats["true_positives"] / (stats["true_positives"] + stats["false_positives"])
        print(f"  📈 Precision:          {precision:.1%}")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
