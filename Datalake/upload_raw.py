"""
Stockage des documents bruts dans la Raw zone (bucket MinIO)
"""

import sys
import os
from datetime import datetime
from minio import Minio

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

BUCKET = "raw"


def upload_to_raw(local_file_path: str):
    if not os.path.exists(local_file_path):
        print(f" Fichier introuvable : {local_file_path}")
        sys.exit(1)

    today    = datetime.today().strftime("%Y-%m-%d")
    filename = os.path.basename(local_file_path)
    obj_name = f"{today}/{filename}"

    print(f" Upload de '{filename}' → {BUCKET}/{obj_name} ...")
    client.fput_object(BUCKET, obj_name, local_file_path)
    print(f" Fichier stocké dans la Raw zone : {BUCKET}/{obj_name}")
    return obj_name


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python upload_raw.py <chemin_du_fichier>")
        sys.exit(1)
    upload_to_raw(sys.argv[1])
