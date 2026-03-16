# Dataset Synthétique – Hackathon 2026

Générateur de documents administratifs français synthétiques pour l'entraînement et l'évaluation d'un pipeline IA de détection d'incohérences documentaires.

---

## Objectif

Créer un jeu de données réaliste simulant les documents reçus par une entreprise lors d'un onboarding fournisseur :

- **Factures**, **Devis**, **Attestation URSSAF**, **Extrait Kbis**, **RIB**
- Documents légitimes ET frauduleux/incohérents
- Versions PDF propres ET versions "scan dégradé" (flou, rotation, bruit, effet smartphone…)

---

## Installation

```bash
pip install -r requirements.txt
```

> Aucune dépendance système requise (PyMuPDF rend les PDF nativement, pas besoin de Poppler).

---

## Générer le dataset

```bash
# Dataset standard (200 train + 50 test, PDF uniquement)
python generate_dataset.py

# Avec images dégradées (scans simulés)
python generate_dataset.py --degrade

# Personnaliser la taille
python generate_dataset.py --n_train 500 --n_test 100 --degrade
```

---

## Structure de sortie

```
output/
├── labels/
│   ├── dataset_<timestamp>.json   ← ground truth complet
│   └── dataset_<timestamp>.csv    ← résumé tabulaire
├── train/
│   ├── raw/                       ← PDFs originaux
│   │   ├── legitime_complet_0000/
│   │   │   ├── facture.pdf
│   │   │   ├── devis.pdf
│   │   │   ├── attestation_urssaf.pdf
│   │   │   ├── kbis.pdf
│   │   │   └── rib.pdf
│   │   └── ...
│   └── degraded/                  ← JPEGs dégradés (si --degrade)
│       └── legitime_complet_0000/
│           ├── facture_p1_smartphone.jpg
│           └── ...
└── test/
    ├── raw/
    └── degraded/
```

---

## Scénarios disponibles

| Scénario | Documents | Anomalies | Poids |
|---|---|---|---|
| `legitime_complet` | facture + devis + attestation + kbis + rib | aucune | 30 |
| `legitime_minimal` | facture + attestation | aucune | 20 |
| `attestation_expiree` | facture + attestation | attestation expirée | 12 |
| `siret_incoherent_facture_attestation` | facture + attestation | SIRET différent entre les deux | 12 |
| `tva_incoherente` | facture + attestation | TVA calculée au mauvais taux | 8 |
| `montant_falsifie` | facture | TTC affiché ≠ HT + TVA | 8 |
| `rib_incoherent` | facture + attestation + rib | IBAN du RIB ≠ IBAN facture | 8 |
| `facture_sans_justificatif` | facture seule | document manquant | 6 |
| `tva_et_montant_falsifies` | facture + attestation | TVA incorrecte + TTC gonflé | 4 |
| `multi_anomalies` | facture + attestation + kbis | SIRET incohérent + attestation expirée | 8 |

**Distribution globale** : ~47% légitimes / ~53% avec anomalies

---

## Profils de dégradation (mode `--degrade`)

| Profil | Effets |
|---|---|
| `light_scan` | Bruit léger + légère flou |
| `medium_scan` | Bruit + rotation + flou |
| `heavy_scan` | Bruit + rotation + flou fort + jaunissement |
| `pixelized` | Pixelisation (compression basse résolution) |
| `smartphone` | Rotation + flou + bruit + ombre + jaunissement + contraste bas |
| `shadow_scan` | Bruit + flou + ombre de coin |

---

## Format des labels (JSON)

```json
{
  "scenario_id": "rib_incoherent_0042",
  "scenario_type": "rib_incoherent",
  "split": "train",
  "anomalies_attendues": ["rib_incoherent"],
  "fournisseur": { "nom": "...", "siret": "12345678901234", "tva": "FR..." },
  "client":      { "nom": "...", "siret": "98765432109876" },
  "documents": [
    {
      "type": "facture",
      "num_facture": "FAC-2026-XXXX",
      "total_ht": 8500.00,
      "taux_tva": 0.20,
      "tva_amount_real": 1700.00,
      "total_ttc_real": 10200.00,
      "anomalies": { "montant_falsifie": false, "tva_incoherente": false }
    },
    {
      "type": "rib",
      "iban_reel": "FR76...",
      "iban_affiche": "FR76... (différent)",
      "anomalies": { "rib_incoherent": true }
    }
  ]
}
```

---

## Architecture du code

```
generate_dataset.py          ← Point d'entrée CLI
│
├── scenarios/
│   └── scenario_builder.py  ← Assemble les scénarios multi-documents
│
├── generators/
│   ├── company.py           ← Données entreprise (SIRET/TVA/IBAN Luhn-valides)
│   ├── facture.py           ← PDF Facture (avec flags fraude)
│   ├── devis.py             ← PDF Devis
│   ├── attestation_urssaf.py← PDF Attestation URSSAF (expirée / SIRET faux)
│   ├── kbis.py              ← PDF Extrait Kbis
│   └── rib.py               ← PDF RIB (avec flag IBAN substitué)
│
└── degradation/
    └── image_degrader.py    ← 6 profils de simulation scan/smartphone
```

---

## Personnalisation avec les noms des binômes

Les noms de l'équipe sont intégrés dans `generators/company.py` dans la liste `BINOMES`. Les entreprises générées avec `use_binome=True` (fournisseurs) utilisent ces noms pour personnaliser les documents.

Pour mettre à jour avec les vrais prénoms :

```python
# generators/company.py
BINOMES = ["Prénom1", "Prénom2", "Prénom3", "Prénom4", "Prénom5", "Prénom6"]
```
