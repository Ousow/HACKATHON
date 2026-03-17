from minio import Minio
from pathlib import Path

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

OCR_OUTPUT = Path("ocr-app/data/output")

total_clean   = 0
total_curated = 0

for file in OCR_OUTPUT.iterdir():
    if file.suffix == ".txt":
        client.fput_object("clean", file.name, str(file))
        total_clean += 1
        print(f"   clean ← {file.name}")

    elif file.suffix == ".json":
        client.fput_object("curated", file.name, str(file))
        total_curated += 1
        print(f"   curated ← {file.name}")

print(f"\n Clean   : {total_clean} fichiers uploadés")
print(f" Curated : {total_curated} fichiers uploadés")