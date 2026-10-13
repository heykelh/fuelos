"""Couche Silver : positions par minute, intervalles qualifiés, bilans par vol et par phase.

Règles appliquées (issues des journaux et diagnostics qualité) :
    R1 : intervalles à plus de 2 h du vol exclus (Q08)
    R2 : positions aberrantes filtrées (Q13)
    R3 : phase déduite de la trajectoire, pas des heures de la liste des vols
    R4 : intervalle couvert à moins de 50 % : phase indéterminée, aucune interpolation
    R5 : vol sans trajectoire téléchargée : phase « Sans trajectoire »
    R6 : débits calculés par vol et par phase, pas par intervalle (quantification)
    R7 : erreur d'unité kg / livre testée par type, signalée et corrigée dans une colonne
         séparée, la valeur brute est conservée
    R8 : Mach non utilisé (champ incomplet, défectueux pour l'A359)

Produit :
    silver.traj_minutes, silver.fuel_intervals, silver.flight_units,
    silver.unit_test, silver.flight_phases
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

LB_IN_KG = 0.45359237
STEP_20LB_KG = 20 * LB_IN_KG
CORRECTION_FACTOR = 1 / LB_IN_KG
MIN_CRUISE_MIN = 30
MIN_FLIGHTS = 20
RATIO_LOW = 0.40
RATIO_HIGH = 0.50
SUSPECT_SHARE = 0.7

MIN_PHASE_MIN = 15
RATE_Z_MAX = 4.0
MIN_CELL = 20

SHOWN_PHASES = ("Montée", "Croisière", "Descente")
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
    avg(latitude) AS lat,
    avg(longitude) AS lon
FROM bronze.trajectories
WHERE (altitude IS NULL OR altitude BETWEEN {ALT_MIN_FT} AND {ALT_MAX_FT})
    AND (groundspeed IS NULL OR groundspeed <= {GS_MAX_KT})
    AND (latitude IS NULL OR latitude BETWEEN -90 AND 90)
    AND (longitude IS NULL OR longitude BETWEEN -180 AND 180)
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
tf AS (
    SELECT DISTINCT flight_id FROM silver.traj_minutes
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
        avg(m.tas_kt) AS tas_mean_kt
    FROM base b
    JOIN silver.traj_minutes m
        ON m.flight_id = b.flight_id
        AND m.minute >= date_trunc('minute', b.t_start)
        AND m.minute <= b.t_end
    GROUP BY b.split, b.idx
)
SELECT
    b.*,
    tf.flight_id IS NOT NULL AS has_trajectory,
    abs(b.fuel_kg / {STEP_20LB_KG} - round(b.fuel_kg / {STEP_20LB_KG})) < 0.02
        AND abs(b.fuel_kg / 10 - round(b.fuel_kg / 10)) > 0.001 AS lb_step,
    coalesce(s.covered_min, 0) AS covered_min,
    {COVERAGE_EXPR} AS coverage,
    s.alt_mean_ft,
    s.alt_first_ft,
    s.alt_last_ft,
    s.gs_mean_kt,
    s.tas_mean_kt,
    {ALT_RATE_EXPR} AS alt_rate_fpm,
    CASE
        WHEN tf.flight_id IS NULL THEN 'Sans trajectoire'
        WHEN {COVERAGE_EXPR} < {COVERAGE_MIN} THEN 'Indéterminée'
        WHEN s.gs_mean_kt < {GROUND_GS_KT} THEN 'Sol'
        WHEN {ALT_RATE_EXPR} > {CLIMB_FPM} THEN 'Montée'
        WHEN {ALT_RATE_EXPR} < -{CLIMB_FPM} THEN 'Descente'
        WHEN s.alt_mean_ft >= {CRUISE_ALT_FT} THEN 'Croisière'
        ELSE 'Palier bas'
    END AS phase
FROM base b
LEFT JOIN tf ON tf.flight_id = b.flight_id
LEFT JOIN stats s ON s.split = b.split AND s.idx = b.idx
"""

CRUISE_PER_FLIGHT = f"""
    SELECT
        flight_id,
        sum(fuel_kg) / (sum(duration_min) / 60) AS kg_per_h
    FROM silver.fuel_intervals_base
    WHERE phase = 'Croisière'
    GROUP BY flight_id
    HAVING sum(duration_min) >= {MIN_CRUISE_MIN}
"""

FLIGHT_UNITS = """
CREATE OR REPLACE TABLE silver.flight_units AS
SELECT
    flight_id,
    any_value(aircraft_type) AS aircraft_type,
    count(*) AS n_intervals,
    avg(CAST(lb_step AS INTEGER)) AS share_lb_step,
    CASE WHEN avg(CAST(lb_step AS INTEGER)) >= 0.5 THEN 'lb' ELSE 'autre' END AS unit_pattern
FROM silver.fuel_intervals_base
GROUP BY flight_id
"""

UNIT_TEST = f"""
CREATE OR REPLACE TABLE silver.unit_test AS
WITH fr AS ({CRUISE_PER_FLIGHT}),
g AS (
    SELECT
        u.aircraft_type,
        count(*) FILTER (WHERE u.unit_pattern = 'lb') AS n_lb,
        count(*) FILTER (WHERE u.unit_pattern <> 'lb') AS n_other,
        median(fr.kg_per_h) FILTER (WHERE u.unit_pattern = 'lb') AS med_lb,
        median(fr.kg_per_h) FILTER (WHERE u.unit_pattern <> 'lb') AS med_other
    FROM fr
    JOIN silver.flight_units u ON u.flight_id = fr.flight_id
    GROUP BY u.aircraft_type
)
SELECT
    *,
    med_lb / med_other AS ratio,
    coalesce(
        n_lb >= {MIN_FLIGHTS}
        AND n_other >= {MIN_FLIGHTS}
        AND med_lb / med_other BETWEEN {RATIO_LOW} AND {RATIO_HIGH},
        false
    ) AS unit_error
FROM g
"""

INTERVALS_FINAL = f"""
CREATE OR REPLACE TABLE silver.fuel_intervals AS
WITH fr AS ({CRUISE_PER_FLIGHT}),
flag AS (
    SELECT
        u.flight_id,
        u.unit_pattern,
        coalesce(
            t.unit_error
            AND u.unit_pattern = 'lb'
            AND (fr.kg_per_h IS NULL OR fr.kg_per_h < {SUSPECT_SHARE} * t.med_other),
            false
        ) AS unit_suspect
    FROM silver.flight_units u
    LEFT JOIN silver.unit_test t ON t.aircraft_type = u.aircraft_type
    LEFT JOIN fr ON fr.flight_id = u.flight_id
)
SELECT
    b.*,
    f.unit_pattern,
    f.unit_suspect,
    CASE WHEN f.unit_suspect THEN b.fuel_kg * {CORRECTION_FACTOR}
        ELSE b.fuel_kg END AS fuel_kg_corr,
    CASE WHEN f.unit_suspect THEN b.kg_per_h * {CORRECTION_FACTOR}
        ELSE b.kg_per_h END AS kg_per_h_corr
FROM silver.fuel_intervals_base b
JOIN flag f ON f.flight_id = b.flight_id
"""

FLIGHT_PHASES = f"""
CREATE OR REPLACE TABLE silver.flight_phases AS
WITH p AS (
    SELECT
        flight_id,
        phase,
        any_value(split) AS split,
        any_value(aircraft_type) AS aircraft_type,
        any_value(category) AS category,
        any_value(unit_suspect) AS unit_suspect,
        count(*) AS n_intervals,
        sum(duration_min) AS duration_min,
        sum(fuel_kg) AS fuel_kg_raw,
        sum(fuel_kg_corr) AS fuel_kg,
        sum(fuel_kg) / (sum(duration_min) / 60) AS kg_per_h_raw,
        sum(fuel_kg_corr) / (sum(duration_min) / 60) AS kg_per_h,
        median(alt_mean_ft) AS alt_ft,
        avg(gs_mean_kt) AS gs_kt
    FROM silver.fuel_intervals
    WHERE phase NOT IN ('Indéterminée', 'Sans trajectoire')
    GROUP BY flight_id, phase
),
ref AS (
    SELECT aircraft_type, phase, median(ln(kg_per_h)) AS med_log, count(*) AS n
    FROM p
    WHERE duration_min >= {MIN_PHASE_MIN}
    GROUP BY aircraft_type, phase
),
mad AS (
    SELECT
        p.aircraft_type,
        p.phase,
        any_value(ref.med_log) AS med_log,
        any_value(ref.n) AS n,
        median(abs(ln(p.kg_per_h) - ref.med_log)) AS mad_log
    FROM p
    JOIN ref ON ref.aircraft_type = p.aircraft_type AND ref.phase = p.phase
    WHERE p.duration_min >= {MIN_PHASE_MIN}
    GROUP BY p.aircraft_type, p.phase
)
SELECT
    p.*,
    p.duration_min >= {MIN_PHASE_MIN} AS reliable,
    CASE
        WHEN p.duration_min >= {MIN_PHASE_MIN} AND mad.n >= {MIN_CELL} AND mad.mad_log > 0
        THEN (ln(p.kg_per_h) - mad.med_log) / (1.4826 * mad.mad_log)
    END AS rate_z,
    coalesce(abs(rate_z) > {RATE_Z_MAX}, false) AS outlier
FROM p
LEFT JOIN mad ON mad.aircraft_type = p.aircraft_type AND mad.phase = p.phase
"""


def fmt(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:_.1f}".replace("_", " ").replace(".", ",")
    return f"{value:_}".replace("_", " ")


def pct(part: float, total: float) -> str:
    if not total:
        return "n.d."
    return f"{part / total * 100:.1f}".replace(".", ",") + " %"


def dec(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n.d."
    return f"{value:.{digits}f}".replace(".", ",")


def step(con, label: str, sql: str) -> None:
    started = time.perf_counter()
    con.execute(sql)
    print(f"  {label:<40} {time.perf_counter() - started:>6.0f} s")


def scope_section(con) -> list[str]:
    lines = [
        "## Répartition des intervalles par phase (vols avec trajectoire)",
        "",
        "| Catégorie | Phase | Intervalles | Part |",
        "|---|---|---:|---:|",
    ]
    for category, phase, n, total in con.execute(
        """
        WITH c AS (
            SELECT category, phase, count(*) AS n
            FROM silver.fuel_intervals
            WHERE has_trajectory
            GROUP BY category, phase
        )
        SELECT category, phase, n, sum(n) OVER (PARTITION BY category) AS total
        FROM c
        ORDER BY category, n DESC
        """
    ).fetchall():
        lines.append(f"| {category} | {phase} | {fmt(n)} | {pct(n, total)} |")

    lines += ["", "Intervalles sans trajectoire téléchargée :", ""]
    for split, n in con.execute(
        "SELECT split, count(*) FROM silver.fuel_intervals "
        "WHERE NOT has_trajectory GROUP BY 1 ORDER BY 1"
    ).fetchall():
        lines.append(f"- {split} : {fmt(n)}")
    return lines


def verdict(n_lb: int, n_other: int, ratio: float | None, unit_error: bool) -> str:
    if unit_error:
        return "Erreur d'unité probable"
    if n_lb < MIN_FLIGHTS or n_other < MIN_FLIGHTS or ratio is None:
        return "Échantillon insuffisant"
    if 0.85 <= ratio <= 1.15:
        return "Pas d'écart"
    return "À examiner"


def unit_section(con) -> list[str]:
    lines = [
        "",
        "## Test d'unité kg / livre (règle R7)",
        "",
        "Vols « motif livre » : au moins la moitié des valeurs sont des multiples exacts de "
        "20 lb. Débit de croisière calculé par vol. Rapport attendu en cas de confusion "
        f"d'unité : {dec(LB_IN_KG, 4)}.",
        "",
        "| Type | Vols motif livre | Autres vols | Croisière motif livre (kg/h) "
        "| Croisière autres (kg/h) | Rapport | Verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for type_code, n_lb, n_other, med_lb, med_other, ratio, unit_error in con.execute(
        """
        SELECT aircraft_type, n_lb, n_other, med_lb, med_other, ratio, unit_error
        FROM silver.unit_test
        ORDER BY n_lb + n_other DESC
        LIMIT 12
        """
    ).fetchall():
        lb_txt = fmt(round(med_lb)) if med_lb is not None else "n.d."
        other_txt = fmt(round(med_other)) if med_other is not None else "n.d."
        lines.append(
            f"| {type_code} | {fmt(n_lb)} | {fmt(n_other)} | {lb_txt} | {other_txt} "
            f"| {dec(ratio)} | {verdict(n_lb, n_other, ratio, unit_error)} |"
        )

    lines += [
        "",
        "Vols corrigés (valeur brute conservée dans fuel_kg, valeur corrigée dans fuel_kg_corr) :",
        "",
        "| Type | Vols corrigés | Vols du type | Part |",
        "|---|---:|---:|---:|",
    ]
    for type_code, flagged, total in con.execute(
        """
        WITH f AS (
            SELECT DISTINCT flight_id, aircraft_type, unit_suspect
            FROM silver.fuel_intervals
        )
        SELECT aircraft_type, count(*) FILTER (WHERE unit_suspect), count(*)
        FROM f
        GROUP BY 1
        HAVING count(*) FILTER (WHERE unit_suspect) > 0
        ORDER BY 2 DESC
        """
    ).fetchall():
        lines.append(f"| {type_code} | {fmt(flagged)} | {fmt(total)} | {pct(flagged, total)} |")
    return lines


def before_after_section(con) -> list[str]:
    lines = [
        "",
        "## Effet de la correction sur la croisière",
        "",
        "| Type | Vols | Médiane brute (kg/h) | Médiane corrigée (kg/h) |",
        "|---|---:|---:|---:|",
    ]
    medians = {}
    for type_code, n, raw, corrected in con.execute(
        """
        SELECT aircraft_type, count(*), median(kg_per_h_raw), median(kg_per_h)
        FROM silver.flight_phases
        WHERE phase = 'Croisière' AND reliable
        GROUP BY 1
        HAVING aircraft_type IN ('A20N', 'A320', 'A21N', 'A321')
        ORDER BY 1
        """
    ).fetchall():
        medians[type_code] = corrected
        lines.append(
            f"| {type_code} | {fmt(n)} | {fmt(round(raw))} | {fmt(round(corrected))} |"
        )
    if "A20N" in medians and "A320" in medians:
        gap = 1 - medians["A20N"] / medians["A320"]
        lines += [
            "",
            f"Après correction, la croisière médiane de l'A20N est inférieure de "
            f"{dec(gap * 100, 1)} % à celle de l'A320.",
        ]
    return lines


def phase_rates_section(con) -> list[str]:
    lines = [
        "",
        "## Débit médian par vol et par phase (kg/h, après correction)",
        "",
        f"Format : médiane (nombre de vols). Phases d'au moins {MIN_PHASE_MIN} min par vol. "
        f"Cellules de moins de {MIN_CELL} vols non affichées. Valeurs atypiques exclues.",
        "",
        "| Type | " + " | ".join(SHOWN_PHASES) + " |",
        "|---|" + "---:|" * len(SHOWN_PHASES),
    ]
    types = [
        r[0]
        for r in con.execute(
            "SELECT aircraft_type FROM silver.flight_phases WHERE reliable "
            "GROUP BY 1 ORDER BY count(DISTINCT flight_id) DESC LIMIT 12"
        ).fetchall()
    ]
    for type_code in types:
        cells = []
        for phase in SHOWN_PHASES:
            median, n = con.execute(
                "SELECT median(kg_per_h), count(*) FROM silver.flight_phases "
                "WHERE aircraft_type = ? AND phase = ? AND reliable AND NOT outlier",
                [type_code, phase],
            ).fetchone()
            cells.append(f"{fmt(round(median))} ({fmt(n)})" if n >= MIN_CELL else "n.d.")
        lines.append(f"| {type_code} | " + " | ".join(cells) + " |")
    return lines


def main() -> int:
    con = connect()
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")

    print("Couche Silver")
    step(con, "Positions nettoyées par minute", TRAJ_MINUTES)
    step(con, "Intervalles qualifiés par phase", INTERVALS_BASE)
    step(con, "Motif d'unité par vol", FLIGHT_UNITS)
    step(con, "Test d'unité par type", UNIT_TEST)
    step(con, "Intervalles avec correction d'unité", INTERVALS_FINAL)
    step(con, "Bilans par vol et par phase", FLIGHT_PHASES)
    con.execute("DROP TABLE silver.fuel_intervals_base")

    lines = [
        "# Phases de vol et débits carburant (couche Silver)",
        "",
        "Phase déduite de la trajectoire de chaque intervalle carburant : vitesse sol moyenne "
        f"inférieure à {GROUND_GS_KT} kt : sol ; variation d'altitude supérieure à {CLIMB_FPM} "
        f"ft/min : montée ou descente ; sinon altitude moyenne d'au moins {CRUISE_ALT_FT} ft : "
        "croisière, en dessous : palier bas. Intervalle couvert à moins de "
        f"{COVERAGE_MIN:.0%} par la trajectoire : indéterminé.",
        "",
        "Les débits sont calculés par vol et par phase, car le carburant est relevé par "
        "paliers (souvent 100 kg ou 20 lb) : sur un intervalle de 5 minutes, ce pas domine "
        "la mesure.",
        "",
    ]
    lines += scope_section(con)
    lines += unit_section(con)
    lines += before_after_section(con)
    lines += phase_rates_section(con)

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    print("\n" + "\n".join(lines))
    print(f"\nRapport écrit : {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
