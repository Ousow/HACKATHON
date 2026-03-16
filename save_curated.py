"""
Stockage des données structurées et validées dans la Curated zone.
"""

import sys
import json
from datetime import datetime
from hdfs import InsecureClient

HDFS_URL      = "http://localhost:9870"
CURATED_ZONE  = "/datalake/curated"

client = InsecureClient(HDFS_URL, user="root")


def save_to_curated(document_id: str, structured_data: dict):

    today      = datetime.today().strftime("%Y-%m-%d")
    hdfs_dir   = f"{CURATED_ZONE}/{today}"
    hdfs_path  = f"{hdfs_dir}/{document_id}.json"

    client.makedirs(hdfs_dir)

    json_content = json.dumps(structured_data, ensure_ascii=False, indent=2)

    print(f" Sauvegarde données structurées → {hdfs_path} ...")
    with client.write(hdfs_path, encoding="utf-8", overwrite=True) as writer:
        writer.write(json_content)

    print(f" Données stockées dans la Curated zone : {hdfs_path}")
    return hdfs_path


def read_from_curated(document_id: str, date: str = None) -> dict:
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    hdfs_path = f"{CURATED_ZONE}/{date}/{document_id}.json"

    print(f" Lecture depuis la Curated zone : {hdfs_path} ...")
    with client.read(hdfs_path, encoding="utf-8") as reader:
        data = json.load(reader)

    print(f" Données récupérées pour '{document_id}'")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage : python save_curated.py <document_id> '<json_data>'")
        sys.exit(1)

    doc_id = sys.argv[1]
    try:
        data = json.loads(sys.argv[2])
    except json.JSONDecodeError:
        print(" Le 2ème argument doit être un JSON valide")
        sys.exit(1)

    save_to_curated(doc_id, data)
