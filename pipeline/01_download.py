"""Téléchargement du jeu PRC Data Challenge 2025 depuis Zenodo vers la couche Bronze.

Usage :
    python pipeline/01_download.py --list
    python pipeline/01_download.py --only .parquet readme
    python pipeline/01_download.py --only flights_train --extract
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import time
import zipfile
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from config import BRONZE_PRC_DIR, ZENODO_RECORD_ID, ensure_dirs

API_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"
MANIFEST_PATH = BRONZE_PRC_DIR / "_zenodo_manifest.json"
CHUNK_SIZE = 1024 * 1024
DOWNLOAD_ATTEMPTS = 5
TIMEOUT = (15, 120)


class IntegrityError(Exception):
    """Fichier téléchargé dont la taille ou l'empreinte MD5 ne correspond pas."""


def build_session() -> requests.Session:
    """Session HTTP avec nouvelles tentatives automatiques sur les erreurs serveur."""
    retry = Retry(
        total=6,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "fuelos/0.1 (github.com/heykelh/fuelos)"
    return session


def parse_files(record: dict) -> list[dict]:
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


def fetch_files(session: requests.Session) -> list[dict]:
    """Liste des fichiers Zenodo, avec repli sur le manifeste local si l'API est indisponible."""
    try:
        response = session.get(API_URL, timeout=TIMEOUT)
        response.raise_for_status()
        files = parse_files(response.json())
        MANIFEST_PATH.write_text(json.dumps(files, indent=2), encoding="utf-8")
        return files
    except requests.RequestException as exc:
        if MANIFEST_PATH.exists():
            print(f"API Zenodo indisponible ({exc.__class__.__name__}), manifeste local utilisé.")
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        raise SystemExit(
            "API Zenodo indisponible et aucun manifeste local. Réessaie dans quelques minutes."
        ) from exc


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


def download_once(session: requests.Session, file: dict, target: Path) -> None:
    """Une tentative de téléchargement, avec reprise à partir du fichier partiel."""
    part = target.with_name(target.name + ".part")
    start = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={start}-"} if start else {}

    with session.get(file["url"], headers=headers, stream=True, timeout=TIMEOUT) as response:
        if response.status_code != 416:
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
        raise IntegrityError(f"Contrôle d'intégrité échoué pour {file['name']}")


def download(session: requests.Session, file: dict, dest_dir: Path) -> Path:
    """Télécharge un fichier avec plusieurs tentatives et contrôle d'intégrité."""
    target = dest_dir / file["name"]
    if is_valid(target, file):
        print(f"Déjà présent et vérifié : {target.name}")
        return target

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            download_once(session, file, target)
            print(f"Téléchargé et vérifié : {target.name}")
            return target
        except (requests.RequestException, IntegrityError) as exc:
            if attempt == DOWNLOAD_ATTEMPTS:
                raise SystemExit(
                    f"Échec définitif pour {file['name']} après {attempt} tentatives : {exc}"
                ) from exc
            wait = 15 * attempt
            print(f"Tentative {attempt} échouée ({exc.__class__.__name__}), reprise dans {wait} s")
            time.sleep(wait)
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
    session = build_session()
    files = fetch_files(session)
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
        path = download(session, f, BRONZE_PRC_DIR)
        if args.extract:
            extract(path, BRONZE_PRC_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
