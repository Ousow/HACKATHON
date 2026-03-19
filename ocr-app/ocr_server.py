import sys
import tempfile
from pathlib import Path
from flask import Flask, jsonify, request

sys.path.insert(0, "/app/app")

from ocr_runner import extract_text_from_image, extract_text_from_pdf
from field_extractor import extract_fields

app = Flask(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/process", methods=["POST"])
def process():
    return ocr()

@app.route("/ocr", methods=["POST"])
def ocr():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu."}), 400

    file = request.files["file"]
    suffix = Path(file.filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Format non supporté : {suffix}"}), 415

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002, debug=False)