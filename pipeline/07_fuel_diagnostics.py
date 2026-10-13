"""Diagnostic du carburant mesuré : quantification, A20N, Mach, coordonnées manquantes.

Hypothèses testées :
    H1 : le carburant est relevé par paliers (100 kg), d'où un plateau à 2 400 kg/h
    H2 : une partie des vols A20N transmet la valeur d'un seul moteur (distribution bimodale)
    H3 : agréger la croisière par vol dilue l'effet de quantification
    H4 : le champ Mach est défectueux pour certains types
    H5 : le filtre Silver a exclu des positions sans coordonnées mais exploitables

Produit docs/diagnostic_carburant.md

Usage :
    python pipeline/07_fuel_diagnostics.py
"""

from __future__ import annotations

import sys

from config import ROOT
from db import connect

REPORT_PATH = ROOT / "docs" / "diagnostic_carburant.md"
FOCUS_TYPES = ("A20N", "A320", "B738", "A21N")
FOCUS_SQL = ", ".join(f"'{t}'" for t in FOCUS_TYPES)
MIN_CRUISE_MIN = 30
BUCKET_KG_H = 250


def fmt(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:_.1f}".replace("_", " ").replace(".", ",")
    return f"{value:_}".replace("_", " ")


def pct(value: float | None) -> str:
    if value is None:
        return "n.d."
    return f"{value * 100:.1f}".replace(".", ",") + " %"


def granularity_section(con) -> list[str]:
    lines = [
        "## H1 : résolution des valeurs de carburant",
        "",
        "Part des intervalles dont la valeur est un multiple exact de 10, 50 ou 100 kg.",
        "",
        "| Type | Intervalles | Multiple de 10 | Multiple de 50 | Multiple de 100 "
        "| Durée médiane (min) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for type_code, n, m10, m50, m100, duration in con.execute(
        """
        SELECT
            aircraft_type,
            count(*) AS n,
            avg(CASE WHEN abs(fuel_kg - 10 * round(fuel_kg / 10)) < 0.01 THEN 1 ELSE 0 END),
            avg(CASE WHEN abs(fuel_kg - 50 * round(fuel_kg / 50)) < 0.01 THEN 1 ELSE 0 END),
            avg(CASE WHEN abs(fuel_kg - 100 * round(fuel_kg / 100)) < 0.01 THEN 1 ELSE 0 END),
            median(duration_min)
        FROM silver.fuel_intervals
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 12
        """
    ).fetchall():
        lines.append(
            f"| {type_code} | {fmt(n)} | {pct(m10)} | {pct(m50)} | {pct(m100)} "
            f"| {fmt(float(duration))} |"
        )

    lines += [
        "",
        "Valeurs les plus fréquentes en croisière :",
        "",
        "| Type | Valeur (kg) | Intervalles | Part de la croisière du type |",
        "|---|---:|---:|---:|",
    ]
    for type_code, value, n, total in con.execute(
        f"""
        WITH v AS (
            SELECT aircraft_type, round(fuel_kg, 1) AS value, count(*) AS n
            FROM silver.fuel_intervals
            WHERE phase = 'Croisière' AND aircraft_type IN ({FOCUS_SQL})
            GROUP BY aircraft_type, round(fuel_kg, 1)
        ),
        r AS (
            SELECT
                *,
                sum(n) OVER (PARTITION BY aircraft_type) AS total,
                row_number() OVER (PARTITION BY aircraft_type ORDER BY n DESC) AS rk
            FROM v
        )
        SELECT aircraft_type, value, n, total FROM r WHERE rk <= 5
        ORDER BY aircraft_type, rk
        """
    ).fetchall():
        lines.append(f"| {type_code} | {fmt(float(value))} | {fmt(n)} | {pct(n / total)} |")
    return lines


def per_flight_section(con) -> list[str]:
    lines = [
        "",
        "## H2 : A20N et A320, débit de croisière calculé par vol",
        "",
        f"Débit = carburant total de croisière / durée totale de croisière, pour les vols "
        f"ayant au moins {MIN_CRUISE_MIN} min de croisière mesurée.",
        "",
        "| Tranche de débit (kg/h) | Vols A20N | Vols A320 |",
        "|---|---:|---:|",
    ]
    for bucket, a20n, a320 in con.execute(
        f"""
        WITH f AS (
            SELECT
                aircraft_type,
                flight_id,
                sum(fuel_kg) / (sum(duration_min) / 60) AS kg_per_h
            FROM silver.fuel_intervals
            WHERE phase = 'Croisière' AND aircraft_type IN ('A20N', 'A320')
            GROUP BY aircraft_type, flight_id
            HAVING sum(duration_min) >= {MIN_CRUISE_MIN}
        )
        SELECT
            floor(kg_per_h / {BUCKET_KG_H}) * {BUCKET_KG_H} AS bucket,
            count(*) FILTER (WHERE aircraft_type = 'A20N'),
            count(*) FILTER (WHERE aircraft_type = 'A320')
        FROM f
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall():
        low = int(bucket)
        lines.append(f"| {fmt(low)} à {fmt(low + BUCKET_KG_H)} | {fmt(a20n)} | {fmt(a320)} |")
    return lines


def aggregation_section(con) -> list[str]:
    lines = [
        "",
        "## H3 : effet de l'agrégation par vol sur la dispersion",
        "",
        "| Type | Vols | P10 par vol | Médiane par vol | P90 par vol |",
        "|---|---:|---:|---:|---:|",
    ]
    for type_code, n, p10, p50, p90 in con.execute(
        f"""
        WITH f AS (
            SELECT
                aircraft_type,
                flight_id,
                sum(fuel_kg) / (sum(duration_min) / 60) AS kg_per_h
            FROM silver.fuel_intervals
            WHERE phase = 'Croisière'
            GROUP BY aircraft_type, flight_id
            HAVING sum(duration_min) >= {MIN_CRUISE_MIN}
        )
        SELECT
            aircraft_type,
            count(*) AS n,
            quantile_cont(kg_per_h, 0.1),
            median(kg_per_h),
            quantile_cont(kg_per_h, 0.9)
        FROM f
        GROUP BY 1
        HAVING count(*) >= 30
        ORDER BY n DESC
        LIMIT 12
        """
    ).fetchall():
        lines.append(
            f"| {type_code} | {fmt(n)} | {fmt(round(p10))} | {fmt(round(p50))} "
            f"| {fmt(round(p90))} |"
        )
    return lines


def speed_section(con) -> list[str]:
    lines = [
        "",
        "## H4 : vitesses mesurées en croisière",
        "",
        "| Type | Intervalles | Mach médian | Part Mach vide | Vitesse vraie médiane (kt) "
        "| Vitesse sol médiane (kt) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for type_code, n, mach, mach_null, tas, gs in con.execute(
        """
        SELECT
            aircraft_type,
            count(*) AS n,
            median(mach_mean),
            avg(CASE WHEN mach_mean IS NULL THEN 1 ELSE 0 END),
            median(tas_mean_kt),
            median(gs_mean_kt)
        FROM silver.fuel_intervals
        WHERE phase = 'Croisière'
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 12
        """
    ).fetchall():
        mach_txt = f"{mach:.2f}".replace(".", ",") if mach is not None else "n.d."
        tas_txt = fmt(round(tas)) if tas is not None else "n.d."
        gs_txt = fmt(round(gs)) if gs is not None else "n.d."
        lines.append(
            f"| {type_code} | {fmt(n)} | {mach_txt} | {pct(mach_null)} | {tas_txt} | {gs_txt} |"
        )
    return lines


def coordinates_section(con) -> list[str]:
    lines = [
        "",
        "## H5 : positions sans coordonnées",
        "",
        "| Source | Positions | Sans latitude ou longitude | Sans altitude |",
        "|---|---:|---:|---:|",
    ]
    for source, n, no_coord, no_alt in con.execute(
        """
        SELECT
            source,
            count(*),
            count(*) FILTER (WHERE latitude IS NULL OR longitude IS NULL),
            count(*) FILTER (WHERE altitude IS NULL)
        FROM bronze.trajectories
        GROUP BY 1
        ORDER BY 2 DESC
        """
    ).fetchall():
        lines.append(f"| {source} | {fmt(n)} | {pct(no_coord / n)} | {pct(no_alt / n)} |")

    audit_minutes = con.execute("SELECT count(*) FROM audit.traj_minutes").fetchone()[0]
    silver_minutes = con.execute("SELECT count(*) FROM silver.traj_minutes").fetchone()[0]
    lines += [
        "",
        f"- Minutes de trajectoire avant filtrage (audit) : {fmt(audit_minutes)}",
        f"- Minutes de trajectoire après filtrage (Silver) : {fmt(silver_minutes)}",
        f"- Minutes perdues : {pct(1 - silver_minutes / audit_minutes)}",
    ]
    return lines


def main() -> int:
    con = connect(read_only=True)
    lines = [
        "# Diagnostic du carburant mesuré",
        "",
        "Objectif : comprendre trois signaux observés en Silver (plateau à 2 400 kg/h, "
        "A20N deux fois plus bas que l'A320, Mach incohérent) avant toute publication.",
        "",
    ]
    lines += granularity_section(con)
    lines += per_flight_section(con)
    lines += aggregation_section(con)
    lines += speed_section(con)
    lines += coordinates_section(con)

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    print("\n".join(lines))
    print(f"\nDiagnostic écrit : {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
