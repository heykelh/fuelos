"""Couche Silver : positions nettoyées par minute et intervalles carburant qualifiés par phase.

Règles appliquées (issues du journal et du diagnostic qualité) :
    R1 : intervalles à plus de 2 h du vol exclus (Q08)
    R2 : positions aberrantes filtrées (Q13)
    R3 : phase déduite de la trajectoire, pas des heures de la liste des vols
    R4 : intervalle couvert à moins de 50 % : phase indéterminée, aucune interpolation
    R5 : débit atypique recalculé par type avion et par phase

Produit :
    silver.traj_minutes
    silver.fuel_intervals
    docs/phases_vol.md

Usage :
    python pipeline/06_silver_intervals.py
"""

from __future__ import annotations

import sys
import time

from config import ROOT, WIDEBODY_TYPES
from db import connect

REPORT_PATH = ROOT / "docs" / "phases_vol.md"

ALT_MIN_FT = -1500
ALT_MAX_FT = 50000
GS_MAX_KT = 750
WINDOW_H = 2
COVERAGE_MIN = 0.5
GROUND_GS_KT = 40
CLIMB_FPM = 300
CRUISE_ALT_FT = 20000
RATE_Z_MAX = 5.0
MIN_CELL = 30

PHASES = ("Montée", "Croisière", "Descente", "Palier bas", "Sol", "Indéterminée")
WIDEBODY_SQL = ", ".join(f"'{t}'" for t in WIDEBODY_TYPES)

TRAJ_MINUTES = f"""
CREATE OR REPLACE TABLE silver.traj_minutes AS
SELECT
    flight_id,
    split,
    date_trunc('minute', "timestamp") AS minute,
    count(*) AS n_pos,
    avg(altitude) AS alt_ft,
    avg(vertical_rate) AS vr_fpm,
    avg(groundspeed) AS gs_kt,
    avg(TAS) AS tas_kt,
    avg(mach) AS mach,
    avg(latitude) AS lat,
    avg(longitude) AS lon
FROM bronze.trajectories
WHERE (altitude IS NULL OR altitude BETWEEN {ALT_MIN_FT} AND {ALT_MAX_FT})
    AND (groundspeed IS NULL OR groundspeed <= {GS_MAX_KT})
    AND latitude BETWEEN -90 AND 90
    AND longitude BETWEEN -180 AND 180
GROUP BY ALL
"""

COVERAGE_EXPR = "least(1, coalesce(s.covered_min, 0) / greatest(1, ceil(b.duration_min)))"
ALT_RATE_EXPR = "(s.alt_last_ft - s.alt_first_ft) / b.duration_min"

INTERVALS_BASE = f"""
CREATE OR REPLACE TABLE silver.fuel_intervals_base AS
WITH base AS (
    SELECT
        f.split,
        f.idx,
        f.flight_id,
        l.aircraft_type,
        CASE WHEN l.aircraft_type IN ({WIDEBODY_SQL})
            THEN 'Long-courrier' ELSE 'Court et moyen-courrier' END AS category,
        f.start AS t_start,
        f."end" AS t_end,
        (epoch(f."end") - epoch(f.start)) / 60 AS duration_min,
        f.fuel_kg,
        f.fuel_kg / ((epoch(f."end") - epoch(f.start)) / 3600) AS kg_per_h
    FROM bronze.fuel f
    JOIN bronze.flightlist l ON l.flight_id = f.flight_id
    WHERE f."end" > f.start
        AND f.fuel_kg > 0
        AND f.start <= l.landed + INTERVAL {WINDOW_H} HOUR
        AND f."end" >= l.takeoff - INTERVAL {WINDOW_H} HOUR
),
stats AS (
    SELECT
        b.split,
        b.idx,
        count(m.minute) AS covered_min,
        avg(m.alt_ft) AS alt_mean_ft,
        arg_min(m.alt_ft, m.minute) AS alt_first_ft,
        arg_max(m.alt_ft, m.minute) AS alt_last_ft,
        avg(m.gs_kt) AS gs_mean_kt,
        avg(m.tas_kt) AS tas_mean_kt,
        avg(m.mach) AS mach_mean
    FROM base b
    JOIN silver.traj_minutes m
        ON m.flight_id = b.flight_id
        AND m.minute >= date_trunc('minute', b.t_start)
        AND m.minute <= b.t_end
    GROUP BY b.split, b.idx
)
SELECT
    b.*,
    coalesce(s.covered_min, 0) AS covered_min,
    {COVERAGE_EXPR} AS coverage,
    s.alt_mean_ft,
    s.alt_first_ft,
    s.alt_last_ft,
    s.gs_mean_kt,
    s.tas_mean_kt,
    s.mach_mean,
    {ALT_RATE_EXPR} AS alt_rate_fpm,
    CASE
        WHEN {COVERAGE_EXPR} < {COVERAGE_MIN} THEN 'Indéterminée'
        WHEN s.gs_mean_kt < {GROUND_GS_KT} THEN 'Sol'
        WHEN {ALT_RATE_EXPR} > {CLIMB_FPM} THEN 'Montée'
        WHEN {ALT_RATE_EXPR} < -{CLIMB_FPM} THEN 'Descente'
        WHEN s.alt_mean_ft >= {CRUISE_ALT_FT} THEN 'Croisière'
        ELSE 'Palier bas'
    END AS phase
FROM base b
LEFT JOIN stats s ON s.split = b.split AND s.idx = b.idx
"""

INTERVALS_FINAL = f"""
CREATE OR REPLACE TABLE silver.fuel_intervals AS
WITH ref AS (
    SELECT aircraft_type, phase, median(ln(kg_per_h)) AS med_log, count(*) AS n
    FROM silver.fuel_intervals_base
    GROUP BY ALL
),
mad AS (
    SELECT
        f.aircraft_type,
        f.phase,
        any_value(r.med_log) AS med_log,
        any_value(r.n) AS n,
        median(abs(ln(f.kg_per_h) - r.med_log)) AS mad_log
    FROM silver.fuel_intervals_base f
    JOIN ref r ON r.aircraft_type = f.aircraft_type AND r.phase = f.phase
    GROUP BY f.aircraft_type, f.phase
)
SELECT
    f.*,
    CASE WHEN m.n >= {MIN_CELL} AND m.mad_log > 0
        THEN (ln(f.kg_per_h) - m.med_log) / (1.4826 * m.mad_log) END AS rate_z,
    coalesce(abs(rate_z) > {RATE_Z_MAX}, false) AS rate_outlier
FROM silver.fuel_intervals_base f
JOIN mad m ON m.aircraft_type = f.aircraft_type AND m.phase = f.phase
"""


def fmt(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:_.1f}".replace("_", " ").replace(".", ",")
    return f"{value:_}".replace("_", " ")


def pct(part: int, total: int) -> str:
    if not total:
        return "n.d."
    return f"{part / total * 100:.1f}".replace(".", ",") + " %"


def step(con, label: str, sql: str) -> None:
    started = time.perf_counter()
    con.execute(sql)
    print(f"  {label:<40} {time.perf_counter() - started:>6.0f} s")


def phase_section(con) -> list[str]:
    lines = [
        "## Répartition des intervalles par phase",
        "",
        "| Catégorie | Phase | Intervalles | Part | Débits atypiques |",
        "|---|---|---:|---:|---:|",
    ]
    rows = con.execute(
        """
        WITH c AS (
            SELECT
                category,
                phase,
                count(*) AS n,
                count(*) FILTER (WHERE rate_outlier) AS outliers
            FROM silver.fuel_intervals
            GROUP BY category, phase
        )
        SELECT category, phase, n, outliers, sum(n) OVER (PARTITION BY category) AS total
        FROM c
        ORDER BY category, n DESC
        """
    ).fetchall()
    for category, phase, n, outliers, total in rows:
        lines.append(
            f"| {category} | {phase} | {fmt(n)} | {pct(n, int(total))} | {fmt(outliers)} |"
        )
    return lines


def rate_section(con) -> list[str]:
    shown = ("Montée", "Croisière", "Descente", "Palier bas", "Sol")
    lines = [
        "",
        "## Débit carburant médian par type et par phase (kg/h)",
        "",
        f"Format : médiane (effectif). Cellules de moins de {MIN_CELL} intervalles non affichées. "
        "Débits atypiques exclus.",
        "",
        "| Type | " + " | ".join(shown) + " |",
        "|---|" + "---:|" * len(shown),
    ]
    types = [
        r[0]
        for r in con.execute(
            "SELECT aircraft_type FROM silver.fuel_intervals "
            "GROUP BY 1 ORDER BY count(*) DESC LIMIT 12"
        ).fetchall()
    ]
    for type_code in types:
        cells = []
        for phase in shown:
            median, n = con.execute(
                "SELECT median(kg_per_h), count(*) FROM silver.fuel_intervals "
                "WHERE aircraft_type = ? AND phase = ? AND NOT rate_outlier",
                [type_code, phase],
            ).fetchone()
            cells.append(f"{fmt(round(median))} ({fmt(n)})" if n >= MIN_CELL else "n.d.")
        lines.append(f"| {type_code} | " + " | ".join(cells) + " |")
    return lines


def cruise_section(con) -> list[str]:
    lines = [
        "",
        "## Croisière : dispersion du débit par type",
        "",
        "| Type | Intervalles | P10 | Médiane | P90 | Mach médian | Altitude médiane (ft) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for type_code, n, p10, p50, p90, mach, alt in con.execute(
        f"""
        SELECT
            aircraft_type,
            count(*) AS n,
            quantile_cont(kg_per_h, 0.1),
            median(kg_per_h),
            quantile_cont(kg_per_h, 0.9),
            median(mach_mean),
            median(alt_mean_ft)
        FROM silver.fuel_intervals
        WHERE phase = 'Croisière' AND NOT rate_outlier
        GROUP BY 1
        HAVING count(*) >= {MIN_CELL}
        ORDER BY n DESC
        LIMIT 12
        """
    ).fetchall():
        mach_txt = f"{mach:.2f}".replace(".", ",") if mach is not None else "n.d."
        lines.append(
            f"| {type_code} | {fmt(n)} | {fmt(round(p10))} | {fmt(round(p50))} "
            f"| {fmt(round(p90))} | {mach_txt} | {fmt(round(alt))} |"
        )
    return lines


def main() -> int:
    con = connect()
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")

    print("Couche Silver")
    step(con, "Positions nettoyées par minute", TRAJ_MINUTES)
    step(con, "Intervalles qualifiés par phase", INTERVALS_BASE)
    step(con, "Débits atypiques par type et phase", INTERVALS_FINAL)
    con.execute("DROP TABLE silver.fuel_intervals_base")

    lines = [
        "# Phases de vol et débits carburant (couche Silver)",
        "",
        "Phase déduite de la trajectoire de chaque intervalle carburant. Règles : vitesse sol "
        f"moyenne inférieure à {GROUND_GS_KT} kt : sol ; variation d'altitude supérieure à "
        f"{CLIMB_FPM} ft/min : montée ou descente ; sinon altitude moyenne supérieure ou égale "
        f"à {CRUISE_ALT_FT} ft : croisière, inférieure : palier bas. Intervalle couvert à moins "
        f"de {COVERAGE_MIN:.0%} par la trajectoire : phase indéterminée.",
        "",
    ]
    lines += phase_section(con)
    lines += rate_section(con)
    lines += cruise_section(con)

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    print("\n" + "\n".join(lines))
    print(f"\nRapport écrit : {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
