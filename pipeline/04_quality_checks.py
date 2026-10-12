"""Contrôles qualité de la couche Bronze PRC 2025.

Produit :
    audit.traj_minutes       : positions agrégées par vol et par minute
    audit.traj_flights       : profil de trajectoire par vol
    audit.fuel_coverage      : couverture de chaque intervalle carburant par la trajectoire
    audit.fuel_rate_outliers : intervalles au débit carburant atypique pour leur type avion
    audit.quality_report     : synthèse des contrôles
    docs/journal_qualite.md  : journal lisible, versionné dans le dépôt

Usage :
    python pipeline/04_quality_checks.py
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime

from config import BRONZE_PRC_DIR, ROOT
from db import connect

REPORT_PATH = ROOT / "docs" / "journal_qualite.md"
FINAL_SUBMIT = (BRONZE_PRC_DIR / "fuel_final_submit.parquet").as_posix()

ALT_MIN_FT = -1500
ALT_MAX_FT = 50000
GS_MAX_KT = 750
GAP_MAX_MIN = 10
COVERAGE_MIN = 0.5
RATE_Z_MAX = 5.0
WINDOW_H = 2

TRAJ_MINUTES = f"""
CREATE OR REPLACE TABLE audit.traj_minutes AS
SELECT
    flight_id,
    split,
    date_trunc('minute', "timestamp") AS minute,
    count(*) AS n_pos,
    count(*) FILTER (WHERE source = 'adsb') AS n_adsb,
    count(*) FILTER (WHERE source = 'acars') AS n_acars,
    count(*) FILTER (WHERE altitude < {ALT_MIN_FT} OR altitude > {ALT_MAX_FT}) AS n_bad_alt,
    count(*) FILTER (WHERE groundspeed > {GS_MAX_KT}) AS n_bad_gs,
    count(*) FILTER (
        WHERE latitude NOT BETWEEN -90 AND 90 OR longitude NOT BETWEEN -180 AND 180
    ) AS n_bad_coord,
    count(*) FILTER (WHERE latitude IS NULL OR longitude IS NULL) AS n_null_coord,
    any_value(typecode) AS typecode
FROM bronze.trajectories
GROUP BY ALL
"""

TRAJ_FLIGHTS = """
CREATE OR REPLACE TABLE audit.traj_flights AS
WITH m AS (
    SELECT
        *,
        epoch(minute - lag(minute) OVER (PARTITION BY flight_id ORDER BY minute)) / 60
            AS gap_min
    FROM audit.traj_minutes
)
SELECT
    flight_id,
    any_value(split) AS split,
    min(minute) AS first_minute,
    max(minute) AS last_minute,
    count(*) AS n_minutes,
    sum(n_pos) AS n_pos,
    sum(n_adsb) AS n_adsb,
    sum(n_acars) AS n_acars,
    sum(n_bad_alt + n_bad_gs + n_bad_coord) AS n_bad_pos,
    sum(n_null_coord) AS n_null_coord,
    coalesce(max(gap_min), 0) AS max_gap_min,
    mode(typecode) AS typecode
FROM m
GROUP BY flight_id
"""

FUEL_COVERAGE = """
CREATE OR REPLACE TABLE audit.fuel_coverage AS
SELECT
    f.split,
    f.idx,
    f.flight_id,
    greatest(1, ceil((epoch(f."end") - epoch(f.start)) / 60)) AS interval_min,
    count(m.minute) AS covered_min
FROM bronze.fuel f
LEFT JOIN audit.traj_minutes m
    ON m.flight_id = f.flight_id
    AND m.minute >= date_trunc('minute', f.start)
    AND m.minute <= f."end"
WHERE f.flight_id IN (SELECT flight_id FROM audit.traj_flights)
GROUP BY ALL
"""

FUEL_RATE_OUTLIERS = f"""
CREATE OR REPLACE TABLE audit.fuel_rate_outliers AS
WITH r AS (
    SELECT
        f.split,
        f.idx,
        f.flight_id,
        l.aircraft_type,
        f.fuel_kg / ((epoch(f."end") - epoch(f.start)) / 3600) AS kg_per_h
    FROM bronze.fuel f
    JOIN bronze.flightlist l ON l.flight_id = f.flight_id
    WHERE f."end" > f.start AND f.fuel_kg > 0
),
med AS (
    SELECT aircraft_type, median(ln(kg_per_h)) AS med_log
    FROM r
    GROUP BY aircraft_type
),
mad AS (
    SELECT
        r.aircraft_type,
        any_value(med.med_log) AS med_log,
        median(abs(ln(r.kg_per_h) - med.med_log)) AS mad_log,
        count(*) AS n
    FROM r
    JOIN med ON med.aircraft_type = r.aircraft_type
    GROUP BY r.aircraft_type
)
SELECT
    r.*,
    exp(mad.med_log) AS type_median_kg_per_h,
    (ln(r.kg_per_h) - mad.med_log) / (1.4826 * mad.mad_log) AS robust_z
FROM r
JOIN mad ON mad.aircraft_type = r.aircraft_type
WHERE mad.n >= 30
    AND mad.mad_log > 0
    AND abs((ln(r.kg_per_h) - mad.med_log) / (1.4826 * mad.mad_log)) > {RATE_Z_MAX}
"""


@dataclass
class Check:
    code: str
    label: str
    anomalies_sql: str
    total_sql: str
    severity: str
    treatment: str
    needs_traj: bool = False


CHECKS = [
    Check(
        "Q01",
        "Identifiant de vol en double",
        "SELECT count(*) - count(DISTINCT flight_id) FROM bronze.flightlist",
        "SELECT count(*) FROM bronze.flightlist",
        "Bloquante",
        "Dédoublonnage",
    ),
    Check(
        "Q02",
        "Horaires de vol incohérents (ordre inversé, moins de 10 min, plus de 20 h)",
        "SELECT count(*) FROM bronze.flightlist WHERE landed <= takeoff "
        "OR landed - takeoff < INTERVAL 10 MINUTE OR landed - takeoff > INTERVAL 20 HOUR",
        "SELECT count(*) FROM bronze.flightlist",
        "Majeure",
        "Vol exclu des analyses par vol",
    ),
    Check(
        "Q03",
        "Aéroport de départ ou d'arrivée absent du référentiel",
        "SELECT count(*) FROM bronze.flightlist l "
        "WHERE NOT EXISTS (SELECT 1 FROM bronze.airports a WHERE a.icao = l.origin_icao) "
        "OR NOT EXISTS (SELECT 1 FROM bronze.airports a WHERE a.icao = l.destination_icao)",
        "SELECT count(*) FROM bronze.flightlist",
        "Mineure",
        "Enrichissement par une source ouverte",
    ),
    Check(
        "Q04",
        "Intervalle carburant en double",
        "SELECT count(*) FROM (SELECT split, idx FROM bronze.fuel "
        "GROUP BY ALL HAVING count(*) > 1)",
        "SELECT count(*) FROM bronze.fuel",
        "Bloquante",
        "Dédoublonnage",
    ),
    Check(
        "Q05",
        "Intervalle de durée nulle ou négative",
        'SELECT count(*) FROM bronze.fuel WHERE "end" <= start',
        "SELECT count(*) FROM bronze.fuel",
        "Bloquante",
        "Intervalle exclu",
    ),
    Check(
        "Q06",
        "Carburant nul, négatif ou manquant",
        "SELECT count(*) FROM bronze.fuel WHERE fuel_kg IS NULL OR fuel_kg <= 0",
        "SELECT count(*) FROM bronze.fuel",
        "Bloquante",
        "Intervalle exclu",
    ),
    Check(
        "Q07",
        "Intervalles qui se chevauchent dans un même vol",
        'SELECT count(*) FROM (SELECT start, lag("end") OVER '
        "(PARTITION BY split, flight_id ORDER BY start) AS prev_end FROM bronze.fuel) "
        "WHERE start < prev_end",
        "SELECT count(*) FROM bronze.fuel",
        "Majeure",
        "Signalé, exclu des cumuls par vol",
    ),
    Check(
        "Q08",
        f"Intervalle à plus de {WINDOW_H} h avant le décollage ou après l'atterrissage",
        "SELECT count(*) FROM bronze.fuel f JOIN bronze.flightlist l "
        "ON l.flight_id = f.flight_id "
        f"WHERE f.start > l.landed + INTERVAL {WINDOW_H} HOUR "
        f'OR f."end" < l.takeoff - INTERVAL {WINDOW_H} HOUR',
        "SELECT count(*) FROM bronze.fuel",
        "Majeure",
        "Intervalle exclu",
    ),
    Check(
        "Q09",
        f"Débit carburant atypique pour le type avion (écart robuste supérieur à {RATE_Z_MAX})",
        "SELECT count(*) FROM audit.fuel_rate_outliers",
        'SELECT count(*) FROM bronze.fuel WHERE "end" > start AND fuel_kg > 0',
        "Majeure",
        "Revue manuelle avant exclusion",
    ),
    Check(
        "Q10",
        "Gabarit final différent de l'union des jeux rank et final",
        f"""
        WITH s AS (
            SELECT flight_id, CAST(start AS TIMESTAMP) AS t0, CAST("end" AS TIMESTAMP) AS t1
            FROM read_parquet('{FINAL_SUBMIT}')
        ),
        l AS (
            SELECT flight_id, start AS t0, "end" AS t1
            FROM bronze.fuel WHERE split IN ('rank', 'final')
        )
        SELECT (SELECT count(*) FROM s ANTI JOIN l USING (flight_id, t0, t1))
             + (SELECT count(*) FROM l ANTI JOIN s USING (flight_id, t0, t1))
        """,
        f"SELECT count(*) FROM read_parquet('{FINAL_SUBMIT}')",
        "Majeure",
        "Jeu de test invalide si non nul",
    ),
    Check(
        "Q11",
        "Vol d'entraînement sans trajectoire",
        "SELECT count(*) FROM bronze.flightlist l WHERE split = 'train' "
        "AND NOT EXISTS (SELECT 1 FROM audit.traj_flights t WHERE t.flight_id = l.flight_id)",
        "SELECT count(*) FROM bronze.flightlist WHERE split = 'train'",
        "Majeure",
        "Vol exclu des modèles à base de trajectoire",
        needs_traj=True,
    ),
    Check(
        "Q12",
        "Type avion différent entre liste de vols et trajectoire",
        "SELECT count(*) FROM audit.traj_flights t "
        "JOIN bronze.flightlist l ON l.flight_id = t.flight_id "
        "WHERE t.typecode <> l.aircraft_type",
        "SELECT count(*) FROM audit.traj_flights",
        "Mineure",
        "Liste de vols retenue comme référence",
        needs_traj=True,
    ),
    Check(
        "Q13",
        "Positions aberrantes (altitude, vitesse sol, coordonnées)",
        "SELECT sum(n_bad_pos) FROM audit.traj_flights",
        "SELECT sum(n_pos) FROM audit.traj_flights",
        "Mineure",
        "Positions filtrées",
        needs_traj=True,
    ),
    Check(
        "Q14",
        f"Vol avec un trou de trajectoire de plus de {GAP_MAX_MIN} min",
        f"SELECT count(*) FROM audit.traj_flights WHERE max_gap_min > {GAP_MAX_MIN}",
        "SELECT count(*) FROM audit.traj_flights",
        "Majeure",
        "Aucune interpolation sur ces trous",
        needs_traj=True,
    ),
    Check(
        "Q15",
        f"Intervalle carburant couvert à moins de {COVERAGE_MIN:.0%} par la trajectoire",
        "SELECT count(*) FROM audit.fuel_coverage "
        f"WHERE least(1, covered_min / interval_min) < {COVERAGE_MIN}",
        "SELECT count(*) FROM audit.fuel_coverage",
        "Majeure",
        "Exclu de l'entraînement des modèles à base de trajectoire",
        needs_traj=True,
    ),
]


def fmt(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:_.1f}".replace("_", " ").replace(".", ",")
    return f"{value:_}".replace("_", " ")


def pct(value: float) -> str:
    return f"{value * 100:.2f}".replace(".", ",") + " %"


def step(con, label: str, sql: str) -> None:
    started = time.perf_counter()
    con.execute(sql)
    print(f"  {label:<40} {time.perf_counter() - started:>6.0f} s")


def profile_section(con) -> list[str]:
    acars_share, median_pos = con.execute(
        "SELECT sum(n_acars) / sum(n_pos), median(n_pos) FROM audit.traj_flights"
    ).fetchone()
    median_coverage = con.execute(
        "SELECT median(least(1, covered_min / interval_min)) FROM audit.fuel_coverage"
    ).fetchone()[0]
    lines = [
        "",
        "## Profil des trajectoires",
        "",
        f"- Part des positions issues d'ACARS : {pct(acars_share)}",
        f"- Nombre médian de positions par vol : {fmt(int(median_pos))}",
        f"- Couverture médiane d'un intervalle carburant : {pct(median_coverage)}",
        "",
        "## Débit carburant observé par type avion",
        "",
        "Médiane du débit sur les intervalles mesurés, toutes phases de vol confondues. "
        "Ce n'est pas une consommation de croisière : la décomposition par phase vient "
        "dans la couche Silver.",
        "",
        "| Type | Intervalles | Débit médian (kg/h) |",
        "|---|---:|---:|",
    ]
    for type_code, n, rate in con.execute(
        """
        SELECT l.aircraft_type, count(*) AS n,
            median(f.fuel_kg / ((epoch(f."end") - epoch(f.start)) / 3600))
        FROM bronze.fuel f
        JOIN bronze.flightlist l ON l.flight_id = f.flight_id
        WHERE f."end" > f.start AND f.fuel_kg > 0
        GROUP BY 1 ORDER BY n DESC LIMIT 12
        """
    ).fetchall():
        lines.append(f"| {type_code} | {fmt(n)} | {fmt(round(rate))} |")
    return lines


def main() -> int:
    con = connect()
    has_traj = con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'bronze' AND table_name = 'trajectories'"
    ).fetchone()[0]

    con.execute("CREATE SCHEMA IF NOT EXISTS audit")
    print("Tables d'audit")
    step(con, "Débits carburant atypiques", FUEL_RATE_OUTLIERS)
    if has_traj:
        step(con, "Trajectoires agrégées par minute", TRAJ_MINUTES)
        step(con, "Profil de trajectoire par vol", TRAJ_FLIGHTS)
        step(con, "Couverture des intervalles carburant", FUEL_COVERAGE)

    run_at = datetime.now()
    rows = []
    print("\nContrôles")
    for check in CHECKS:
        if check.needs_traj and not has_traj:
            continue
        if check.code == "Q10" and not (BRONZE_PRC_DIR / "fuel_final_submit.parquet").exists():
            continue
        anomalies = int(con.execute(check.anomalies_sql).fetchone()[0] or 0)
        total = int(con.execute(check.total_sql).fetchone()[0] or 0)
        rate = anomalies / total if total else 0.0
        rows.append(
            (check.code, check.label, anomalies, total, rate,
             check.severity, check.treatment, run_at)
        )
        print(f"  {check.code} {fmt(anomalies):>12} / {fmt(total):<14} {pct(rate):>9}")

    con.execute(
        "CREATE OR REPLACE TABLE audit.quality_report (code VARCHAR, controle VARCHAR, "
        "anomalies BIGINT, perimetre BIGINT, taux DOUBLE, gravite VARCHAR, "
        "traitement VARCHAR, run_at TIMESTAMP)"
    )
    con.executemany("INSERT INTO audit.quality_report VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)

    lines = [
        "# Journal qualité : couche Bronze PRC 2025",
        "",
        f"Exécution du {run_at:%d/%m/%Y à %H:%M}. Source : PRC Data Challenge 2025 "
        "(Eurocontrol, OpenSky Network), DOI 10.5281/zenodo.19184661.",
        "",
        "## Contrôles",
        "",
        "| Code | Contrôle | Anomalies | Périmètre | Taux | Gravité | Traitement en Silver |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for code, label, anomalies, total, rate, severity, treatment, _ in rows:
        lines.append(
            f"| {code} | {label} | {fmt(anomalies)} | {fmt(total)} | {pct(rate)} "
            f"| {severity} | {treatment} |"
        )
    lines += [
        "",
        "Seuils : altitude hors de [-1 500 ; 50 000] ft, vitesse sol supérieure à 750 kt, "
        "écart robuste calculé sur le logarithme du débit avec la médiane et l'écart absolu "
        "médian de chaque type avion (au moins 30 intervalles par type).",
        "",
        "Limite connue : le contrôle Q09 compare des intervalles de phases différentes "
        "(roulage, montée, croisière). Il ne repère que les erreurs grossières. "
        "Un contrôle par phase sera ajouté en Silver.",
    ]
    if has_traj:
        lines += profile_section(con)

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    print(f"\nJournal écrit : {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
