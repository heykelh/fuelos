"""Diagnostic des anomalies Q09, Q14 et Q15 : où se trouvent-elles vraiment ?

Hypothèses testées :
    Q09 : les débits atypiques viennent du mélange entre phases sol et vol
    Q14 : les trous de trajectoire se concentrent sur les long-courriers, en vol
    Q15 : la mauvaise couverture des intervalles suit la même logique que Q14

Produit docs/diagnostic_qualite.md

Usage :
    python pipeline/05_quality_diagnostics.py
"""

from __future__ import annotations

import sys

from config import ROOT
from db import connect

REPORT_PATH = ROOT / "docs" / "diagnostic_qualite.md"
GAP_MAX_MIN = 10
COVERAGE_MIN = 0.5

WIDEBODY_TYPES = (
    "A332", "A333", "A338", "A339", "A343", "A346", "A359", "A35K", "A388",
    "B744", "B748", "B762", "B763", "B764", "B772", "B773", "B77L", "B77W",
    "B788", "B789", "B78X",
)
WIDEBODY_SQL = ", ".join(f"'{t}'" for t in WIDEBODY_TYPES)
CATEGORY_SQL = (
    f"CASE WHEN l.aircraft_type IN ({WIDEBODY_SQL}) "
    "THEN 'Long-courrier' ELSE 'Court et moyen-courrier' END"
)

STAGE_BEFORE = "Sol, avant décollage"
STAGE_AIR = "En vol"
STAGE_AFTER = "Sol, après atterrissage"
STAGE_MIXED = "À cheval sol / vol"

INTERVALS_VIEW = f"""
CREATE OR REPLACE TEMP VIEW intervals AS
SELECT
    f.split,
    f.idx,
    f.flight_id,
    l.aircraft_type,
    {CATEGORY_SQL} AS category,
    CASE
        WHEN f."end" <= l.takeoff THEN '{STAGE_BEFORE}'
        WHEN f.start >= l.landed THEN '{STAGE_AFTER}'
        WHEN f.start >= l.takeoff AND f."end" <= l.landed THEN '{STAGE_AIR}'
        ELSE '{STAGE_MIXED}'
    END AS stage,
    (epoch(f."end") - epoch(f.start)) / 60 AS duration_min,
    f.fuel_kg / ((epoch(f."end") - epoch(f.start)) / 3600) AS kg_per_h
FROM bronze.fuel f
JOIN bronze.flightlist l ON l.flight_id = f.flight_id
WHERE f."end" > f.start AND f.fuel_kg > 0
"""


def fmt(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:_.1f}".replace("_", " ").replace(".", ",")
    return f"{value:_}".replace("_", " ")


def pct(part: int, total: int) -> str:
    if not total:
        return "n.d."
    return f"{part / total * 100:.1f}".replace(".", ",") + " %"


def q09_section(con) -> list[str]:
    lines = [
        "## Q09 : débits atypiques selon la phase",
        "",
        "| Phase | Intervalles | Atypiques bas | Atypiques hauts | Taux atypique |",
        "|---|---:|---:|---:|---:|",
    ]
    for stage, n, low, high in con.execute(
        """
        SELECT
            i.stage,
            count(*) AS n,
            count(o.idx) FILTER (WHERE o.robust_z < 0) AS low,
            count(o.idx) FILTER (WHERE o.robust_z > 0) AS high
        FROM intervals i
        LEFT JOIN audit.fuel_rate_outliers o ON o.split = i.split AND o.idx = i.idx
        GROUP BY 1
        ORDER BY n DESC
        """
    ).fetchall():
        lines.append(f"| {stage} | {fmt(n)} | {fmt(low)} | {fmt(high)} | {pct(low + high, n)} |")
    return lines


def rate_section(con) -> list[str]:
    lines = [
        "",
        "## Débit carburant médian par phase (kg/h)",
        "",
        "Médiane sur les intervalles mesurés entièrement au sol ou entièrement en vol. "
        "Les intervalles à cheval sont exclus.",
        "",
        "| Type | Catégorie | Sol avant décollage | En vol "
        "| Sol après atterrissage | Intervalles |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for type_code, category, before, air, after, n in con.execute(
        f"""
        SELECT
            aircraft_type,
            any_value(category),
            median(kg_per_h) FILTER (WHERE stage = '{STAGE_BEFORE}'),
            median(kg_per_h) FILTER (WHERE stage = '{STAGE_AIR}'),
            median(kg_per_h) FILTER (WHERE stage = '{STAGE_AFTER}'),
            count(*) AS n
        FROM intervals
        WHERE stage <> '{STAGE_MIXED}'
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 12
        """
    ).fetchall():
        cells = [fmt(round(v)) if v is not None else "n.d." for v in (before, air, after)]
        lines.append(f"| {type_code} | {category} | {' | '.join(cells)} | {fmt(n)} |")
    return lines


def q14_section(con) -> list[str]:
    lines = [
        "",
        f"## Q14 : trous de trajectoire de plus de {GAP_MAX_MIN} min",
        "",
        "| Catégorie | Vols | Vols avec trou | Part | Trous en vol | Trous au sol "
        "| Durée médiane d'un trou en vol (min) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category, flights, with_gap, air_gaps, ground_gaps, median_air in con.execute(
        f"""
        WITH m AS (
            SELECT
                flight_id,
                minute,
                lag(minute) OVER (PARTITION BY flight_id ORDER BY minute) AS prev
            FROM audit.traj_minutes
        ),
        g AS (
            SELECT
                m.flight_id,
                epoch(m.minute - m.prev) / 60 AS gap_min,
                CASE
                    WHEN m.minute <= l.takeoff OR m.prev >= l.landed THEN 'sol'
                    ELSE 'vol'
                END AS stage
            FROM m
            JOIN bronze.flightlist l ON l.flight_id = m.flight_id
            WHERE epoch(m.minute - m.prev) / 60 > {GAP_MAX_MIN}
        ),
        f AS (
            SELECT t.flight_id, {CATEGORY_SQL} AS category
            FROM audit.traj_flights t
            JOIN bronze.flightlist l ON l.flight_id = t.flight_id
        )
        SELECT
            f.category,
            count(DISTINCT f.flight_id),
            count(DISTINCT g.flight_id),
            count(g.flight_id) FILTER (WHERE g.stage = 'vol'),
            count(g.flight_id) FILTER (WHERE g.stage = 'sol'),
            median(g.gap_min) FILTER (WHERE g.stage = 'vol')
        FROM f
        LEFT JOIN g ON g.flight_id = f.flight_id
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall():
        median_txt = fmt(round(median_air)) if median_air is not None else "n.d."
        lines.append(
            f"| {category} | {fmt(flights)} | {fmt(with_gap)} | {pct(with_gap, flights)} "
            f"| {fmt(air_gaps)} | {fmt(ground_gaps)} | {median_txt} |"
        )
    return lines


def q15_section(con) -> list[str]:
    lines = [
        "",
        f"## Q15 : intervalles couverts à moins de {COVERAGE_MIN:.0%} par la trajectoire",
        "",
        "| Catégorie | Phase | Intervalles | Mal couverts | Part |",
        "|---|---|---:|---:|---:|",
    ]
    for category, stage, n, bad in con.execute(
        f"""
        SELECT
            i.category,
            i.stage,
            count(*),
            count(*) FILTER (WHERE least(1, c.covered_min / c.interval_min) < {COVERAGE_MIN})
        FROM intervals i
        JOIN audit.fuel_coverage c ON c.split = i.split AND c.idx = i.idx
        GROUP BY ALL
        ORDER BY 1, 2
        """
    ).fetchall():
        lines.append(f"| {category} | {stage} | {fmt(n)} | {fmt(bad)} | {pct(bad, n)} |")
    return lines


def main() -> int:
    con = connect()
    con.execute(INTERVALS_VIEW)

    lines = [
        "# Diagnostic qualité : où se trouvent les anomalies ?",
        "",
        "Objectif : vérifier les hypothèses avant de fixer les règles de passage en Silver. "
        "Phase déduite des heures de décollage et d'atterrissage de la liste des vols.",
        "",
    ]
    lines += q09_section(con)
    lines += rate_section(con)
    lines += q14_section(con)
    lines += q15_section(con)

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    print("\n".join(lines))
    print(f"\nDiagnostic écrit : {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
