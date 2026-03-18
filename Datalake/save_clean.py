"""
Stockage du texte OCR dans la Clean zone (bucket MinIO)
"""

import sys
import io
from datetime import datetime
from minio import Minio

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

BUCKET = "clean"


def save_to_clean(document_id: str, ocr_text: str):
    today    = datetime.today().strftime("%Y-%m-%d")
    obj_name = f"{today}/{document_id}.txt"

    data  = ocr_text.encode("utf-8")
    print(f" Sauvegarde OCR → {BUCKET}/{obj_name} ...")
    client.put_object(BUCKET, obj_name, io.BytesIO(data), length=len(data), content_type="text/plain")
    print(f" Texte OCR stocké dans la Clean zone : {BUCKET}/{obj_name}")
    return obj_name


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage : python save_clean.py <document_id> <texte_ocr>")
        sys.exit(1)
    save_to_clean(sys.argv[1], sys.argv[2])
