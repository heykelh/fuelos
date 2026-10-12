"""Téléchargement du jeu PRC Data Challenge 2025 depuis Zenodo vers la couche Bronze.

Usage :
    python pipeline/01_download.py --list
    python pipeline/01_download.py --only flightlist fuel apt
    python pipeline/01_download.py --extract
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tarfile
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

from config import BRONZE_PRC_DIR, ZENODO_RECORD_ID, ensure_dirs

API_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"
CHUNK_SIZE = 1024 * 1024


def fetch_files() -> list[dict]:
    """Récupère la liste des fichiers publiés sur l'enregistrement Zenodo."""
    response = requests.get(API_URL, timeout=60)
    response.raise_for_status()
    record = response.json()
    files = []
    for item in record.get("files", []):
        checksum = item.get("checksum", "")
        files.append(
            {
                "name": item["key"],
                "size": int(item["size"]),
                "md5": checksum.split(":", 1)[1] if checksum.startswith("md5:") else None,
                "url": item["links"]["self"],
            }
        )
    return files


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("o", "Ko", "Mo", "Go"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} To"


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def is_valid(path: Path, file: dict) -> bool:
    if not path.exists() or path.stat().st_size != file["size"]:
        return False
    return file["md5"] is None or md5sum(path) == file["md5"]


def download(file: dict, dest_dir: Path) -> Path:
    """Télécharge un fichier avec reprise possible et contrôle d'intégrité."""
    target = dest_dir / file["name"]
    if is_valid(target, file):
        print(f"Déjà présent et vérifié : {target.name}")
        return target

    part = target.with_name(target.name + ".part")
    start = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={start}-"} if start else {}

    with requests.get(file["url"], headers=headers, stream=True, timeout=120) as response:
        if response.status_code == 416:
            start = file["size"]
        else:
            response.raise_for_status()
            if start and response.status_code != 206:
                start = 0
            mode = "ab" if start else "wb"
            with (
                part.open(mode) as handle,
                tqdm(
                    total=file["size"],
                    initial=start,
                    unit="B",
                    unit_scale=True,
                    desc=file["name"],
                ) as bar,
            ):
                for chunk in response.iter_content(CHUNK_SIZE):
                    handle.write(chunk)
                    bar.update(len(chunk))

    part.replace(target)
    if not is_valid(target, file):
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Contrôle d'intégrité échoué pour {file['name']}, relance le script.")
    print(f"Téléchargé et vérifié : {target.name}")
    return target


def extract(path: Path, dest_dir: Path) -> None:
    """Décompresse les archives zip ou tar dans la couche Bronze."""
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            archive.extractall(dest_dir)
        print(f"Archive extraite : {path.name}")
    elif path.name.endswith((".tar", ".tar.gz", ".tgz")):
        with tarfile.open(path) as archive:
            archive.extractall(dest_dir, filter="data")
        print(f"Archive extraite : {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Téléchargement du jeu PRC 2025 (Zenodo)")
    parser.add_argument("--list", action="store_true", help="Lister les fichiers sans télécharger")
    parser.add_argument(
        "--only",
        nargs="*",
        default=[],
        help="Ne télécharger que les fichiers dont le nom contient un de ces mots",
    )
    parser.add_argument("--extract", action="store_true", help="Décompresser les archives")
    args = parser.parse_args()

    ensure_dirs()
    files = fetch_files()
    if not files:
        print("Aucun fichier trouvé sur l'enregistrement Zenodo.")
        return 1

    if args.only:
        files = [f for f in files if any(word in f["name"] for word in args.only)]

    total = sum(f["size"] for f in files)
    print(f"{len(files)} fichier(s), {human_size(total)} au total")
    for f in files:
        print(f"  {f['name']:<50} {human_size(f['size']):>10}")

    if args.list:
        return 0

    for f in files:
        path = download(f, BRONZE_PRC_DIR)
        if args.extract:
            extract(path, BRONZE_PRC_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
