

## 🎯 Fonctionnalités

### Détection par règles métier

| Type d'anomalie | Description | Gravité |
|-----------------|-------------|---------|
| `siret_incoherent` | SIRET différent entre facture et attestation | 🔴 CRITICAL |
| `tva_incoherente` | Montant TVA ≠ HT × taux | 🔴 CRITICAL |
| `montant_falsifie` | TTC ≠ HT + TVA | 🔴 CRITICAL |
| `attestation_expiree` | Attestation URSSAF hors validité | 🔴 CRITICAL |
| `rib_incoherent` | IBAN facture ≠ RIB fourni (fraude) | 🔴 CRITICAL |
| `document_manquant` | Pièce justificative absente | 🟠 ERROR |
| `siret_invalide` | Format SIRET incorrect | 🟠 ERROR |
| `iban_invalide` | Format IBAN incorrect | 🟠 ERROR |

### Détection par Machine Learning

- **Algorithme** : Isolation Forest
- **Features** : ratios de montants, écarts de calcul, durées de validité
- **Objectif** : Détecter les patterns inhabituels non couverts par les règles

## 🚀 Démarrage rapide

### Avec Docker

```bash
# Build et lancement
docker build -t validation-service .
docker run -p 8001:8001 validation-service

# Ou via docker-compose (depuis la racine du projet)
docker-compose up validation-service
```

### En local

```bash
cd validation-service
pip install -r requirements.txt

# Lancer le serveur
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## 📡 API REST

### Endpoints principaux

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/validate` | Valider un dossier fournisseur |
| POST | `/validate/batch` | Valider plusieurs dossiers |
| GET | `/health` | Health check |
| GET | `/stats` | Statistiques du service |
| POST | `/demo/validate` | Démonstration avec données test |

### Exemple de requête

```bash
curl -X POST http://localhost:8001/validate \
  -H "Content-Type: application/json" \
  -d '{
    "dossier": {
      "dossier_id": "FOUR-2026-001",
      "facture": {
        "fichier_source": "facture.pdf",
        "numero_facture": "FAC-2026-0001",
        "siret_emetteur": "12345678901234",
        "montant_ht": 1000.00,
        "taux_tva": 0.20,
        "montant_tva": 200.00,
        "montant_ttc": 1200.00,
        "date_emission": "2026-03-15"
      },
      "attestation_urssaf": {
        "fichier_source": "attestation.pdf",
        "numero_attestation": "ATT-123456",
        "siret": "12345678901234",
        "date_edition": "2026-01-01",
        "date_expiration": "2026-06-30"
      }
    },
    "use_ml": true
  }'
```

### Exemple de réponse

```json
{
  "dossier_id": "FOUR-2026-001",
  "est_valide": true,
  "score_confiance": 0.95,
  "anomalies": [],
  "nb_anomalies": 0,
  "nb_critiques": 0,
  "nb_erreurs": 0,
  "nb_warnings": 0,
  "documents_analyses": ["facture", "attestation_urssaf"],
  "documents_manquants": ["devis", "kbis", "rib"],
  "duree_validation_ms": 12.5
}
```

## 🧪 Tests

```bash
cd validation-service
pytest tests/ -v
```

## 📁 Structure du projet

```
validation-service/
├── app/
│   ├── __init__.py
│   ├── main.py                    # API FastAPI
│   ├── models/
│   │   ├── schemas.py             # Modèles Pydantic
│   │   └── anomaly_detector.py    # Modèle ML (Isolation Forest)
│   ├── validators/
│   │   ├── base.py                # Classe abstraite
│   │   ├── siret_validator.py     # Validation SIRET
│   │   ├── tva_validator.py       # Validation TVA
│   │   ├── date_validator.py      # Validation dates
│   │   ├── rib_validator.py       # Validation RIB/IBAN
│   │   └── completeness_validator.py
│   └── services/
│       └── validation_engine.py   # Moteur d'orchestration
├── tests/
│   └── test_validators.py
├── Dockerfile
├── requirements.txt
└── README.md
```

## 🔗 Intégration avec le pipeline

Ce service s'intègre dans le pipeline global :

```
[Upload] → [OCR] → [Extraction NLP] → [VALIDATION] → [Curated Zone] → [Front-end]
                                           ↑
                                     Ce service
```

### Entrée attendue

Les données extraites par l'OCR/NLP doivent être structurées selon les schémas Pydantic :
- `FactureExtrait`
- `AttestationURSSAFExtrait`
- `DevisExtrait`
- `KbisExtrait`
- `RIBExtrait`

### Sortie produite

Un `ResultatValidation` avec :
- Liste des anomalies détectées
- Score de confiance
- Recommandation (valide/invalide)

## 📊 Swagger UI

Documentation interactive disponible sur : `http://localhost:8001/docs`

## 🛠️ Configuration

| Variable | Description | Défaut |
|----------|-------------|--------|
| `USE_ML` | Activer détection ML | `true` |
| `ML_THRESHOLD` | Seuil détection ML | `0.5` |
| `LOG_LEVEL` | Niveau de log | `INFO` |
