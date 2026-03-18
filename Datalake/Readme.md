# Data Lake — MINIO

Infrastructure de stockage structurée en 3 zones, basée sur **MinIO** et conteneurisée via Docker.

---

##  Architecture des zones

```
MinIO
├── raw       ← Documents bruts (PDF, images)
├── clean     ← Texte extrait par l'OCR (.txt)
└── curated   ← Données structurées et validées (.json)
```

| Zone | Alimentée par | Lue par |
|---|---|---|
| `raw` | Front-end (upload utilisateur) | OCR service |
| `clean` | OCR service | Validation service |
| `curated` | Validation service | Front-end |

---

##  Pourquoi MinIO ?

- **Compatible ARM + x86** — fonctionne sur toutes les machines de l'équipe
- **API compatible S3** — standard industriel, intégration native avec Python et Airflow
- **Un seul conteneur Docker** — déploiement simple et rapide
- **Interface web intégrée** — visualisation des fichiers sur `http://localhost:9001`
- **Scalable** — peut gérer des millions de fichiers en mode distribué

---

##  Installation

### Prérequis
- Docker & Docker Compose
- Python 3.9+

### Lancer MinIO

```bash
docker-compose up -d
```

Vérifier sur : `http://localhost:9001`
Login : `minioadmin` / `minioadmin`

### Installer la dépendance Python

```bash
pip install minio
```

---

##  Scripts disponibles

### Uploader les résultats OCR dans MinIO

```bash
python upload_to_minio.py
```

Dispatche automatiquement les fichiers générés par l'OCR :
- `.txt` → bucket `clean`
- `.json` → bucket `curated`

---

##  Sécurisation des accès

| Rôle | raw | clean | curated |
|---|---|---|---|
| OCR service | Lecture | Écriture | — |
| Validation service | — | Lecture | Écriture |
| Front-end | — | — | Lecture |
| Airflow | Tout | Tout | Tout |

Les credentials sont gérés via des variables d'environnement dans le `docker-compose.yml`.

---

##  Ports exposés

| Service | Port | Usage |
|---|---|---|
| MinIO API S3 | 9000 | Connexion Python / Airflow |
| MinIO Console | 9001 | Interface web |

---

##  Variables d'environnement

| Variable | Valeur | Description |
|---|---|---|
| `MINIO_ROOT_USER` | `minioadmin` | Identifiant admin |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | Mot de passe admin |
| `MINIO_ENDPOINT` | `minio:9000` | Endpoint interne Docker |
