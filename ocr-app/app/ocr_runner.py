from pathlib import Path
import json
import sys

from PIL import Image
import pytesseract
from pdf2image import convert_from_path

from preprocessing import preprocess_pil_image, preprocess_pdf_page_for_ocr
from field_extractor import extract_fields


def extract_text_from_image(image_path: Path) -> str:
    image = Image.open(image_path)
    processed_image = preprocess_pil_image(image)

    text = pytesseract.image_to_string(
        processed_image,
        lang="fra",
    )

    return text


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Convertit le PDF en images puis applique un OCR simple et propre.
    On garde aussi les pages prétraitées si output_dir est fourni.
    """
    pages = convert_from_path(pdf_path, dpi=300)
    all_text = []

    for i, page in enumerate(pages, start=1):
        processed_page = preprocess_pdf_page_for_ocr(page)

        text = pytesseract.image_to_string(
            processed_page,
            lang="fra",
        )

        all_text.append(f"--- PAGE {i} ---\n{text}")

    return "\n\n".join(all_text)


def run_ocr(input_file_path: str) -> None:
    input_path = Path(input_file_path)
    
    project_root = Path(__file__).resolve().parent.parent # On remonte de 2 dossier à partir de ce fichier (ocr_runner.py)
    output_dir = project_root / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"Erreur : fichier introuvable -> {input_path}")
        return

    suffix = input_path.suffix.lower()

    try:
        if suffix in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]:
            text = extract_text_from_image(input_path)
        elif suffix == ".pdf":
            text = extract_text_from_pdf(input_path)
        else:
            print(f"Erreur : format non supporté -> {suffix}")
            return

    except Exception as e:
        print(f"Erreur pendant le traitement OCR : {e}")
        return

    output_text_path = output_dir / f"{input_path.stem}_ocr.txt"
    output_text_path.write_text(text, encoding="utf-8")

    extracted_json = extract_fields(text=text, document_name=input_path.name)

    output_json_path = output_dir / f"{input_path.stem}_structured.json"
    output_json_path.write_text(
        json.dumps(extracted_json, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("=== TEXTE OCR ===")
    print(text[:2000])

    print("\n=== JSON EXTRAIT ===")
    print(json.dumps(extracted_json, ensure_ascii=False, indent=2))

    print(f"\nTexte OCR enregistré dans : {output_text_path}")
    print(f"JSON structuré enregistré dans : {output_json_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python app/ocr_runner.py <chemin_complet_du_fichier>")
    else:
        run_ocr(sys.argv[1])