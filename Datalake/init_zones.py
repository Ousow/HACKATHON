"""
Création des 3 zones du Data Lake dans MinIO (buckets S3)
"""

from minio import Minio

# Connexion à MinIO
client = Minio(
    "minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

# Les 3 zones = 3 buckets MinIO
ZONES = [
    "raw",      # Documents bruts (PDF, images)
    "clean",    # Texte extrait par l'OCR
    "curated",  # Données structurées JSON validées
]

def init_zones():
    print(" Initialisation du Data Lake MinIO...\n")
    for zone in ZONES:
        if not client.bucket_exists(zone):
            client.make_bucket(zone)
            print(f"  Bucket créé : {zone}")
        else:
            print(f"   Bucket déjà existant : {zone}")
    print("\n  Data Lake prêt ! Interface web : http://localhost:9001")
    print("  Login : minioadmin / minioadmin")

if __name__ == "__main__":
    init_zones()
