"""
Stockage des données brutes
"""

import sys
import os
from datetime import datetime
from hdfs import InsecureClient

HDFS_URL  = "http://localhost:9870"
RAW_ZONE  = "/datalake/raw"

client = InsecureClient(HDFS_URL, user="root")


def upload_to_raw(local_file_path: str):

    if not os.path.exists(local_file_path):
        print(f" Fichier introuvable : {local_file_path}")
        sys.exit(1)

    # Dossier du jour pour organiser les uploads
    today        = datetime.today().strftime("%Y-%m-%d")
    filename     = os.path.basename(local_file_path)
    hdfs_dir     = f"{RAW_ZONE}/{today}"
    hdfs_path    = f"{hdfs_dir}/{filename}"

    # Créer le dossier du jour si besoin
    client.makedirs(hdfs_dir)

    # Upload
    print(f" Upload de '{filename}' → {hdfs_path} ...")
    with open(local_file_path, "rb") as f:
        client.write(hdfs_path, f, overwrite=True)

    print(f" Fichier stocké dans la Raw zone : {hdfs_path}")
    return hdfs_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python upload_raw.py <chemin_du_fichier>")
        sys.exit(1)

    upload_to_raw(sys.argv[1])
