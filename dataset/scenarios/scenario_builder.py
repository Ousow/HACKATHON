"""
Constructeur de scénarios.
Chaque scénario représente un dossier fournisseur cohérent ou incohérent,
composé de plusieurs documents liés entre eux.
"""
import random
from datetime import date

# Import des générateurs
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from generators.company import generate_company
from generators.facture import generate_facture_pdf
from generators.devis import generate_devis_pdf
from generators.attestation_urssaf import generate_attestation_urssaf_pdf
from generators.kbis import generate_kbis_pdf
from generators.rib import generate_rib_pdf


# ──────────────────────────────────────────────
# Définition des types de scénarios
# ──────────────────────────────────────────────

SCENARIOS = {
    # ── LÉGITIMES ───────────────────────────────
    "legitime_complet": {
        "description": "Dossier fournisseur complet et cohérent",
        "anomalies": [],
        "documents": ["facture", "devis", "attestation_urssaf", "kbis", "rib"],
    },
    "legitime_minimal": {
        "description": "Dossier minimal cohérent (facture + attestation)",
        "anomalies": [],
        "documents": ["facture", "attestation_urssaf"],
    },

    # ── INCOHÉRENCES SIRET ───────────────────────
    "siret_incoherent_facture_attestation": {
        "description": "SIRET différent entre la facture et l'attestation URSSAF",
        "anomalies": ["siret_incoherent"],
        "documents": ["facture", "attestation_urssaf"],
    },

    # ── TVA INCOHÉRENTE ──────────────────────────
    "tva_incoherente": {
        "description": "TVA calculée incorrectement sur la facture",
        "anomalies": ["tva_incoherente"],
        "documents": ["facture", "attestation_urssaf"],
    },

    # ── MONTANT FALSIFIÉ ─────────────────────────
    "montant_falsifie": {
        "description": "Le total TTC affiché ne correspond pas au HT + TVA",
        "anomalies": ["montant_falsifie"],
        "documents": ["facture"],
    },

    # ── ATTESTATION EXPIRÉE ──────────────────────
    "attestation_expiree": {
        "description": "L'attestation URSSAF est hors délai de validité",
        "anomalies": ["attestation_expiree"],
        "documents": ["facture", "attestation_urssaf"],
    },

    # ── MULTI-ANOMALIES ──────────────────────────
    "multi_anomalies": {
        "description": "Plusieurs incohérences simultanées",
        "anomalies": ["siret_incoherent", "attestation_expiree"],
        "documents": ["facture", "attestation_urssaf", "kbis"],
    },
    # ── RIB INCOHÉRENT (fraude RIB) ────────────────────────────
    "rib_incoherent": {
        "description": "L'IBAN du RIB ne correspond pas à celui sur la facture (substitution de compte)",
        "anomalies": ["rib_incoherent"],
        "documents": ["facture", "attestation_urssaf", "rib"],
    },

    # ── FACTURE SANS JUSTIFICATIF ───────────────────────────────
    "facture_sans_justificatif": {
        "description": "Facture seule, sans devis ni attestation URSSAF (dossier incomplet)",
        "anomalies": ["document_manquant"],
        "documents": ["facture"],
    },

    # ── TVA + MONTANT FALSIFIÉS ─────────────────────────────────
    "tva_et_montant_falsifies": {
        "description": "TVA incorrecte ET montant TTC gonflé sur la même facture",
        "anomalies": ["tva_incoherente", "montant_falsifie"],
        "documents": ["facture", "attestation_urssaf"],
    },
}


def build_scenario(
    scenario_name: str,
    output_dir: str,
    scenario_id: int,
    split: str = "train",
) -> dict:
    """
    Construit un scénario complet : génère tous les documents associés.

    Args:
        scenario_name: clé dans SCENARIOS
        output_dir: dossier de sortie racine
        scenario_id: identifiant unique du scénario
        split: "train" ou "test"

    Returns:
        dict complet du scénario avec ground truth
    """
    if scenario_name not in SCENARIOS:
        raise ValueError(f"Scénario inconnu : {scenario_name}")

    config = SCENARIOS[scenario_name]
    anomalies = config["anomalies"]

    # Générer les entreprises
    fournisseur = generate_company(use_binome=True)
    client = generate_company(use_binome=False)

    # Pour les scénarios SIRET incohérent : générer un faux SIRET
    faux_siret = None
    if "siret_incoherent" in anomalies:
        # Générer une entreprise différente et prendre son SIRET
        autre = generate_company()
        faux_siret = autre["siret"]

    # Pour le scénario RIB incohérent : générer un faux IBAN
    faux_iban = None
    if "rib_incoherent" in anomalies:
        autre_banque = generate_company()
        faux_iban = autre_banque["iban"]

    # Dossier de sortie pour ce scénario
    scenario_dir = os.path.join(output_dir, split, "raw", f"{scenario_name}_{scenario_id:04d}")
    os.makedirs(scenario_dir, exist_ok=True)

    documents_generes = []
    scenario_result = {
        "scenario_id": f"{scenario_name}_{scenario_id:04d}",
        "scenario_type": scenario_name,
        "split": split,
        "description": config["description"],
        "anomalies_attendues": anomalies,
        "fournisseur": {
            "nom": fournisseur["nom"],
            "siret": fournisseur["siret"],
            "tva": fournisseur["tva"],
        },
        "client": {
            "nom": client["nom"],
            "siret": client["siret"],
        },
        "documents": [],
    }

    date_ref = date.today()

    for doc_type in config["documents"]:
        path = os.path.join(scenario_dir, f"{doc_type}.pdf")

        if doc_type == "facture":
            meta = generate_facture_pdf(
                path=path,
                emetteur=fournisseur,
                destinataire=client,
                falsify_montant=("montant_falsifie" in anomalies),
                falsify_tva=("tva_incoherente" in anomalies),
            )

        elif doc_type == "devis":
            meta = generate_devis_pdf(
                path=path,
                emetteur=fournisseur,
                destinataire=client,
            )

        elif doc_type == "attestation_urssaf":
            meta = generate_attestation_urssaf_pdf(
                path=path,
                entreprise=fournisseur,
                expired=("attestation_expiree" in anomalies),
                force_siret=faux_siret,
                date_reference=date_ref,
            )

        elif doc_type == "kbis":
            meta = generate_kbis_pdf(
                path=path,
                entreprise=fournisseur,
                date_reference=date_ref,
            )

        elif doc_type == "rib":
            meta = generate_rib_pdf(
                path=path,
                entreprise=fournisseur,
                force_iban=faux_iban,
            )
        else:
            continue

        documents_generes.append(meta)
        scenario_result["documents"].append(meta)

    return scenario_result
