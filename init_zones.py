"""
Création des 3 zones du Data Lake dans HDFS
"""

from hdfs import InsecureClient

# Connexion au NameNode via WebHDFS 
HDFS_URL = "http://localhost:9870"
client = InsecureClient(HDFS_URL, user="root")

#  Définition des zones
ZONES = {
    "raw":      "/datalake/raw",       # Documents bruts (PDF, images)
    "clean":    "/datalake/clean",     # Texte extrait par l'OCR
    "curated":  "/datalake/curated",   # Données structurées JSON validées
}

def init_zones():
    print(" Initialisation du Data Lake HDFS...\n")
    for zone_name, zone_path in ZONES.items():
        if not client.status(zone_path, strict=False):
            client.makedirs(zone_path)
            print(f"  Zone créée : {zone_path}")
        else:
            print(f"   Zone déjà existante : {zone_path}")
    print("\n  Data Lake prêt !")

if __name__ == "__main__":
    init_zones()
