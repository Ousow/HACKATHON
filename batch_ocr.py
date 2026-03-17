import subprocess
from pathlib import Path

FOLDERS = [
    Path("dataset/output/train/raw"),
    Path("dataset/output/test/raw"),
]

SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp", ".pdf"]

def batch_run():
    total   = 0
    success = 0
    errors  = []

    for folder in FOLDERS:
        if not folder.exists():
            print(f"  Dossier introuvable : {folder}")
            continue

        files = [f for f in folder.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS]
        print(f"\n {folder} — {len(files)} fichiers trouvés\n")

        for file in files:
            total += 1
            # Chemin tel que vu depuis le conteneur (/app/...)
            container_path = f"/app/{file.as_posix()}"
            print(f"   {file.parent.name}/{file.name}")

            result = subprocess.run(
                [
                    "docker-compose", "exec", "-T", "ocr-service",
                    "python", "ocr-app/app/ocr_runner.py", container_path
                ],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                success += 1
                print(f"   OK")
            else:
                errors.append(str(file))
                print(f"   Erreur : {result.stderr[:100]}")

    print(f"\n{'='*40}")
    print(f" Succès  : {success}/{total}")
    print(f" Erreurs : {len(errors)}")
    if errors:
        for err in errors:
            print(f"   - {err}")

if __name__ == "__main__":
    batch_run()