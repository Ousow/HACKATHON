# Hackathon 2026 — Pipeline de Gestion Documentaire

## Lancement rapide

### Prérequis
- Docker Desktop installé et lancé

### Lancer tous les services

```bash
docker-compose up --build
```

| Interface | URL |
|---|---|
| Front-end | http://localhost |
| Validation API (Swagger) | http://localhost:8001/docs |
| MinIO Console | http://localhost:9001 |

Login MinIO : `minioadmin` / `minioadmin`

---

## Lancement en local (dev)

### Backend Flask

```bash
pip install -r requirements.txt
pip install flask flask-cors
python server.py
```

### Front-end

```bash
cd front
npm install
npm run dev
```

Front disponible sur `http://localhost:5173`
Ou Localhost si docker-compose up --build 

### Validation service

```bash
cd validation-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## Structure du projet

```
HACKATHON/
├── server.py                  ← Wrapper Flask (pont OCR ↔ front)
├── pipeline.py                ← Orchestration
├── docker-compose.yml         ← Lancement de tous les services
├── Dockerfile.server          ← Image Docker du serveur Flask
├── Dockerfile.front           ← Image Docker du front React
├── Dockerfile.pipeline        ← Image Docker du pipeline
│
├── ocr-app/                   ← Extraction de texte (Tesseract)
│   ├── app/
│   │   ├── ocr_runner.py
│   │   ├── field_extractor.py
│   │   └── preprocessing.py
│   └── Dockerfile
│
├── front/                     ← Interface utilisateur (React + Vite)
│   └── src/
│       ├── pages/
│       │   ├── UploadPage.jsx
│       │   └── ResultPage.jsx
│       └── services/
│           └── api.js
│
├── validation-service/        ← Détection d'anomalies (FastAPI)
│   ├── app/
│   └── Dockerfile
│
├── dataset/                   ← Génération de données synthétiques
│
└── Datalake/                  ← Configuration MinIO
```

---

## Ports

| Service | Port |
|---|---|
| Front-end | 80 |
| Serveur Flask | 5000 |
| Validation service | 8001 |
| MinIO API | 9000 |
| MinIO Console | 9001 |