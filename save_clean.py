"""
Stockage de textes bruts extraits par l'OCR dans la Clean zone.
"""

import sys
import json
from datetime import datetime
from hdfs import InsecureClient

HDFS_URL    = "http://localhost:9870"
CLEAN_ZONE  = "/datalake/clean"

client = InsecureClient(HDFS_URL, user="root")


def save_to_clean(document_id: str, ocr_text: str):
   
    today      = datetime.today().strftime("%Y-%m-%d")
    hdfs_dir   = f"{CLEAN_ZONE}/{today}"
    hdfs_path  = f"{hdfs_dir}/{document_id}.txt"

    client.makedirs(hdfs_dir)

    print(f" Sauvegarde OCR → {hdfs_path} ...")
    with client.write(hdfs_path, encoding="utf-8", overwrite=True) as writer:
        writer.write(ocr_text)

    print(f" Texte OCR stocké dans la Clean zone : {hdfs_path}")
    return hdfs_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage : python save_clean.py <document_id> <texte_ocr>")
        sys.exit(1)

    save_to_clean(sys.argv[1], sys.argv[2])
