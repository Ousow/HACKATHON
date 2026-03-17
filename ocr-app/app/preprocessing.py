import cv2
import numpy as np
from PIL import Image, ImageOps, ImageEnhance


def preprocess_pil_image(pil_image: Image.Image) -> Image.Image:
    """
    Prétraitement simple pour améliorer l'OCR :
    - conversion en niveaux de gris
    - autocontraste
    - léger agrandissement
    - léger débruitage
    - seuillage adaptatif
    """
    # 1) convertir en niveaux de gris
    gray = pil_image.convert("L")

    # 2) améliorer légèrement le contraste
    gray = ImageOps.autocontrast(gray)
    enhancer = ImageEnhance.Contrast(gray)
    gray = enhancer.enhance(1.5)

    # 3) convertir PIL -> OpenCV
    img = np.array(gray)

    # 4) agrandir l'image pour aider Tesseract
    scale_factor = 1.5
    img = cv2.resize(
        img,
        None,
        fx=scale_factor,
        fy=scale_factor,
        interpolation=cv2.INTER_CUBIC
    )

    # 5) léger débruitage
    img = cv2.GaussianBlur(img, (3, 3), 0)

    # 6) seuillage adaptatif
    img = cv2.adaptiveThreshold(
        img,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    # 7) retour en PIL
    return Image.fromarray(img)

def preprocess_pdf_page_for_ocr(image: Image.Image) -> Image.Image:
    """
    Prétraitement léger pour pages issues d'un PDF.
    - conversion en niveaux de gris
    - autocontraste léger
    """
    gray = image.convert("L")
    gray = ImageOps.autocontrast(gray)
    return gray