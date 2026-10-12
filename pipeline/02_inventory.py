"""Inventaire de la couche Bronze PRC 2025 : fichiers, schémas, volumétrie, premiers chiffres.

Usage :
    python pipeline/02_inventory.py
"""

from __future__ import annotations

import sys

import duckdb

from config import BRONZE_PRC_DIR, PARIS_AIRPORTS, ROOT

REPORT_PATH = ROOT / "docs" / "inventaire_bronze.md"


def fmt(value: int | float) -> str:
    """Formate un nombre avec des espaces comme séparateurs de milliers."""
    if isinstance(value, float):
        return f"{value:_.1f}".replace("_", " ")
    return f"{value:_}".replace("_", " ")


def table_section(con: duckdb.DuckDBPyConnection) -> list[str]:
    lines = ["## Tables", "", "| Fichier | Lignes | Colonnes |", "|---|---:|---|"]
    tables = sorted(p for p in BRONZE_PRC_DIR.glob("*.parquet") if not p.name.startswith("prc"))
    for path in tables:
        source = path.as_posix()
        rows = con.execute(f"SELECT count(*) FROM read_parquet('{source}')").fetchone()[0]
        columns = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{source}')").fetchall()
        described = " ; ".join(f"{c[0]} ({c[1]})" for c in columns)
        lines.append(f"| {path.name} | {fmt(rows)} | {described} |")
    return lines


def trajectory_section(con: duckdb.DuckDBPyConnection) -> list[str]:
    lines = ["", "## Trajectoires", "", "| Dossier | Fichiers | Taille |", "|---|---:|---:|"]
    folders = sorted(d for d in BRONZE_PRC_DIR.iterdir() if d.is_dir())
    sample = None
    for folder in folders:
        files = list(folder.rglob("*.parquet"))
        if not files:
            continue
        size_mo = sum(f.stat().st_size for f in files) / 1024**2
        lines.append(f"| {folder.name} | {fmt(len(files))} | {fmt(size_mo)} Mo |")
        sample = sample or files[0]

    if sample is not None:
        source = sample.as_posix()
        columns = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{source}')").fetchall()
        rows = con.execute(f"SELECT count(*) FROM read_parquet('{source}')").fetchone()[0]
        lines += [
            "",
            f"Schéma d'une trajectoire ({sample.name}, {fmt(rows)} positions) :",
            "",
        ]
        lines += [f"- {c[0]} ({c[1]})" for c in columns]
    return lines


def figures_section(con: duckdb.DuckDBPyConnection) -> list[str]:
    flightlists = sorted(BRONZE_PRC_DIR.glob("flightlist_*.parquet"))
    fuel_train = BRONZE_PRC_DIR / "fuel_train.parquet"
    if not flightlists or not fuel_train.exists():
        return []

    flight_sources = ", ".join(f"'{p.as_posix()}'" for p in flightlists)
    fuel_source = fuel_train.as_posix()
    con.execute(
        f"CREATE OR REPLACE VIEW flights AS "
        f"SELECT * FROM read_parquet([{flight_sources}], union_by_name = true)"
    )
    con.execute(
        f"CREATE OR REPLACE VIEW fuel AS SELECT * FROM read_parquet('{fuel_source}')"
    )

    lines = ["", "## Premiers chiffres", ""]

    total = con.execute("SELECT count(DISTINCT flight_id) FROM flights").fetchone()[0]
    lines.append(f"- Vols distincts (toutes listes) : {fmt(total)}")

    fuel_stats = con.execute(
        "SELECT count(*), count(DISTINCT flight_id), sum(fuel_kg), "
        "median(epoch(\"end\") - epoch(start)) FROM fuel"
    ).fetchone()
    lines.append(f"- Intervalles carburant (entraînement) : {fmt(fuel_stats[0])}")
    lines.append(f"- Vols couverts par ces intervalles : {fmt(fuel_stats[1])}")
    lines.append(f"- Carburant total mesuré : {fmt(fuel_stats[2] / 1000)} t")
    lines.append(f"- Durée médiane d'un intervalle : {fmt(fuel_stats[3] / 60)} min")

    orphans = con.execute(
        "SELECT count(DISTINCT f.flight_id) FROM fuel f "
        "LEFT JOIN flights l USING (flight_id) WHERE l.flight_id IS NULL"
    ).fetchone()[0]
    lines.append(f"- Vols du fichier carburant absents des listes de vols : {fmt(orphans)}")

    paris = ", ".join(f"'{code}'" for code in PARIS_AIRPORTS)
    paris_count = con.execute(
        f"SELECT count(DISTINCT flight_id) FROM flights "
        f"WHERE origin_icao IN ({paris}) OR destination_icao IN ({paris})"
    ).fetchone()[0]
    lines.append(f"- Vols au départ ou à l'arrivée de CDG ou ORY : {fmt(paris_count)}")

    lines += ["", "Types avion les plus représentés :", "", "| Type | Vols |", "|---|---:|"]
    for type_code, count in con.execute(
        "SELECT aircraft_type, count(DISTINCT flight_id) AS n FROM flights "
        "GROUP BY 1 ORDER BY n DESC LIMIT 15"
    ).fetchall():
        lines.append(f"| {type_code} | {fmt(count)} |")
    return lines


def main() -> int:
    if not BRONZE_PRC_DIR.exists() or not any(BRONZE_PRC_DIR.glob("*.parquet")):
        print("Couche Bronze vide : lance d'abord pipeline/01_download.py")
        return 1

    con = duckdb.connect()
    lines = ["# Inventaire de la couche Bronze : PRC Data Challenge 2025", ""]
    lines += table_section(con)
    lines += trajectory_section(con)
    lines += figures_section(con)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nRapport écrit : {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
