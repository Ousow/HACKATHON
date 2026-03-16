"""
Stockage des données structurées et validées dans la Curated zone (bucket MinIO)
"""

import sys
import json
import io
import os
from datetime import datetime
from minio import Minio

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

BUCKET = "curated"


def save_to_curated(document_id: str, structured_data: dict):
    today        = datetime.today().strftime("%Y-%m-%d")
    obj_name     = f"{today}/{document_id}.json"
    json_content = json.dumps(structured_data, ensure_ascii=False, indent=2).encode("utf-8")

    print(f" Sauvegarde données structurées → {BUCKET}/{obj_name} ...")
    client.put_object(BUCKET, obj_name, io.BytesIO(json_content), length=len(json_content), content_type="application/json")
    print(f" Données stockées dans la Curated zone : {BUCKET}/{obj_name}")
    return obj_name


def read_from_curated(document_id: str, date: str = None) -> dict:
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")
    obj_name = f"{date}/{document_id}.json"

    print(f" Lecture depuis la Curated zone : {BUCKET}/{obj_name} ...")
    response = client.get_object(BUCKET, obj_name)
    data = json.loads(response.read().decode("utf-8"))
    print(f" Données récupérées pour '{document_id}'")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage : python save_curated.py <document_id> <fichier.json>")
        print("  ou  : python save_curated.py <document_id> '<json_data>'")
        sys.exit(1)

    doc_id = sys.argv[1]
    arg = sys.argv[2]

    # Accepte soit un fichier JSON soit une chaîne JSON directe
    if os.path.isfile(arg):
        with open(arg, encoding="utf-8-sig") as f:
            data = json.load(f)
        save_to_curated(doc_id, data)
        sys.exit(0)

    try:
        data = json.loads(arg)
    except json.JSONDecodeError:
        print(" Le 2ème argument doit être un JSON valide ou un chemin vers un fichier .json")
        sys.exit(1)

    save_to_curated(doc_id, data)
