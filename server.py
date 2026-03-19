import json
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# --- Ajout du dossier contenant ocr_runner.py au path Python ---
OCR_APP_DIR = Path(__file__).resolve().parent / "ocr-app" / "app"
sys.path.insert(0, str(OCR_APP_DIR))

from ocr_runner import extract_text_from_image, extract_text_from_pdf  # noqa: E402
from field_extractor import extract_fields  # noqa: E402

app = Flask(__name__)
CORS(app)  # autorise les requêtes depuis le front Vite (localhost:5173)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


@app.route("/upload", methods=["POST"])
def upload():
    """
    Reçoit un fichier multipart/form-data (clé : "file"),
    lance l'OCR + extraction de champs,
    retourne le JSON structuré.
    """
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu (clé attendue : 'file')."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide."}), 400

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify({
            "error": f"Format non supporté : {suffix}. "
                     f"Formats acceptés : {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 415

    # Sauvegarde temporaire pour que pdf2image / PIL puissent lire le fichier
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        if suffix == ".pdf":
            text = extract_text_from_pdf(tmp_path)
        else:
            text = extract_text_from_image(tmp_path)

        result = extract_fields(text=text, document_name=file.filename)
        return jsonify(result), 200

    except Exception as exc:
        return jsonify({"error": f"Erreur OCR : {str(exc)}"}), 500

    finally:
        tmp_path.unlink(missing_ok=True)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)