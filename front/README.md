# Front-end — Interface de gestion documentaire

Interface utilisateur React permettant de déposer un document, visualiser les champs extraits par OCR, les corriger manuellement et valider le dossier auprès du service de validation.

---

## Stack technique

| Outil | Rôle |
|---|---|
| React 18 | UI et gestion du state |
| Vite | Bundler et serveur de dev |
| React Router | Navigation entre pages |
| lucide-react | Icônes |
| nginx | Serveur de fichiers statiques en prod |

---

## Lancement en local

### Prérequis
- Node.js 18+
- Le serveur Flask (`server.py`) qui doit tourner sur `:5000`
- Le `validation-service` qui doit tourner sur `:8001`

### Installation et démarrage

```bash
cd front
npm install
npm run dev
```

Front disponible sur : `http://localhost:5173`

---

## Lancement via Docker

```bash
# Depuis la racine du projet
docker-compose up --build front server
```

Front disponible sur : `http://localhost`

---

## Structure

```
front/src/
├── pages/
│   ├── UploadPage.jsx          ← Drag & drop + envoi du fichier
│   ├── UploadPage.styles.js    ← Styles de la page upload
│   ├── ResultPage.jsx          ← Formulaire pré-rempli + validation
│   └── ResultPage.styles.js    ← Styles de la page résultat
├── components/
│   └── Navbar.jsx              ← Barre de navigation
├── services/
│   └── api.js                  ← Appel POST /upload vers Flask
├── App.jsx                     ← Routing principal
└── main.jsx                    ← Point d'entrée React
```

---

## Flow de données

```
UploadPage.jsx
    |
    | POST /upload (multipart/form-data)
    v
server.py (Flask :5000)
    |
    | JSON { siret, montants, dates, iban... }
    v
ResultPage.jsx  ←  formulaire pré-rempli, éditable
    |
    | POST /validate (JSON)
    v
validation-service (FastAPI :8001)
    |
    | { est_valide, score_confiance, anomalies[] }
    v
ResultPage.jsx  ←  affichage du résultat
```

---

## Pages

### UploadPage

- Drag & drop avec états visuels (survol, fichier sélectionné, erreur)
- Validation locale avant envoi : format accepté (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tiff`, `.webp`), taille max 20 Mo
- Spinner pendant l'analyse OCR

### ResultPage

- Affiche les champs extraits dans des `<input>` éditables
- Chaque champ a un badge de confiance coloré (vert ≥ 90%, orange ≥ 70%, rouge < 70%)
- Les champs non détectés sont vides et remplissables manuellement
- Bouton **Valider le document** : construit le `DossierFournisseur` selon le type détecté et l'envoie au `validation-service`
- Affiche les anomalies classées par niveau : `CRITICAL`, `ERROR`, `WARNING`
- Section dépliable avec l'aperçu du texte OCR brut et le JSON complet (debug)

---

## Appels API

| Depuis | Vers | Méthode | Description |
|---|---|---|---|
| `api.js` | `localhost:5000/upload` | POST multipart | Envoi du fichier pour OCR |
| `ResultPage.jsx` | `localhost:8001/validate` | POST JSON | Validation du dossier |

---

## Build de production

```bash
cd front
npm run build
```

Les fichiers statiques sont générés dans `front/dist/` et servis par nginx dans le conteneur Docker.