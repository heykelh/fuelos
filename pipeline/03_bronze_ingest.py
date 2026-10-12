"""Ingestion de la couche Bronze PRC 2025 dans DuckDB.

Tables du schéma bronze :
    flightlist   : listes de vols train, rank, final
    fuel         : intervalles carburant mesurés train, rank, final
    airports     : coordonnées et altitude des aéroports
Vue :
    trajectories : positions lues directement dans les fichiers Parquet

Les fichiers *_submit ne sont pas ingérés : ce sont les gabarits de soumission du challenge.
Seule transformation : horodatages convertis de la nanoseconde à la microseconde.

Usage :
    python pipeline/03_bronze_ingest.py
"""

from __future__ import annotations

import sys
import time

from config import BRONZE_PRC_DIR
from db import connect

SPLITS = ("train", "rank", "final")
FUEL_SELECT = '* REPLACE (CAST(start AS TIMESTAMP) AS start, CAST("end" AS TIMESTAMP) AS "end")'
TRAJ_SELECT = '* REPLACE (CAST("timestamp" AS TIMESTAMP) AS "timestamp")'


def fmt(value: int) -> str:
    return f"{value:_}".replace("_", " ")


def union_files(pattern: str, select: str) -> str | None:
    """Assemble les fichiers train, rank, final présents, avec leur origine."""
    parts = []
    for split in SPLITS:
        path = BRONZE_PRC_DIR / pattern.format(split=split)
        if path.exists():
            parts.append(
                f"SELECT {select}, '{split}' AS split, '{path.name}' AS source_file, "
                f"current_timestamp AS ingested_at "
                f"FROM read_parquet('{path.as_posix()}')"
            )
    return " UNION ALL BY NAME ".join(parts) if parts else None


def trajectories_sql() -> str | None:
    """Vue sur les dossiers de trajectoires disponibles, sans copie des données."""
    parts = []
    for split in SPLITS:
        folder = BRONZE_PRC_DIR / f"flights_{split}"
        if folder.is_dir():
            parts.append(
                f"SELECT {TRAJ_SELECT}, '{split}' AS split "
                f"FROM read_parquet('{folder.as_posix()}/**/*.parquet', union_by_name = true)"
            )
    return " UNION ALL BY NAME ".join(parts) if parts else None


def main() -> int:
    if not (BRONZE_PRC_DIR / "flightlist_train.parquet").exists():
        print("Fichiers absents : lance d'abord pipeline/01_download.py")
        return 1

    started = time.perf_counter()
    con = connect()
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    flight_sql = union_files("flightlist_{split}.parquet", "*")
    fuel_sql = union_files("fuel_{split}.parquet", FUEL_SELECT)
    con.execute(f"CREATE OR REPLACE TABLE bronze.flightlist AS {flight_sql}")
    con.execute(f"CREATE OR REPLACE TABLE bronze.fuel AS {fuel_sql}")

    airports = (BRONZE_PRC_DIR / "airports.parquet").as_posix()
    con.execute(
        f"CREATE OR REPLACE TABLE bronze.airports AS "
        f"SELECT *, current_timestamp AS ingested_at FROM read_parquet('{airports}')"
    )

    traj_sql = trajectories_sql()
    if traj_sql:
        con.execute(f"CREATE OR REPLACE VIEW bronze.trajectories AS {traj_sql}")

    print("Couche Bronze chargée dans DuckDB\n")
    for table in ("flightlist", "fuel"):
        for split, rows in con.execute(
            f"SELECT split, count(*) FROM bronze.{table} GROUP BY 1 ORDER BY 1"
        ).fetchall():
            print(f"  bronze.{table:<12} {split:<6} {fmt(rows):>10} lignes")
    airport_rows = con.execute("SELECT count(*) FROM bronze.airports").fetchone()[0]
    print(f"  bronze.airports            {fmt(airport_rows):>10} lignes")

    if traj_sql:
        for split, rows, flights in con.execute(
            "SELECT split, count(*), count(DISTINCT flight_id) "
            "FROM bronze.trajectories GROUP BY 1 ORDER BY 1"
        ).fetchall():
            print(
                f"  bronze.trajectories {split:<6} {fmt(rows):>12} positions, "
                f"{fmt(flights)} vols"
            )

    con.close()
    print(f"\nTerminé en {time.perf_counter() - started:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
