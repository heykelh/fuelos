"""Contrôle d'échelle du carburant mesuré (règle R9, version 2).

Constats :
    - l'A20N consomme environ 45 % de l'A320 sur toutes les phases (facteur constant)
    - sa croisière par vol est bimodale, avec deux groupes séparés d'un facteur proche de 2
    - OpenAP concorde avec la mesure pour l'A320, le B738, l'A332, l'A333, mais il est
      biaisé pour l'A20N et les gros porteurs Boeing : il ne peut pas juger un vol seul

Règle R9 v2 :
    1. pour chaque type, séparation des débits de croisière par vol en deux groupes
       (2-moyennes sur le logarithme du débit)
    2. deux échelles si les centres sont dans un rapport de 1,8 à 2,5 et si le petit
       groupe pèse au moins 10 % des vols
    3. type à deux échelles : OpenAP choisit le groupe le plus plausible ; sans référence
       OpenAP, le type est non tranché
    4. chaque vol est comparé au centre de son échelle retenue : hors de [0,6 ; 1,6],
       échelle suspecte
    Les vols suspects, non tranchés ou non vérifiables sont exclus des chiffres absolus.

Produit :
    silver.cruise_reference, silver.type_scale, silver.flight_scale
    docs/controle_echelle.md

Usage :
    python pipeline/08_scale_check.py
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd
from openap import FuelFlow, prop

from config import ROOT
from db import connect

REPORT_PATH = ROOT / "docs" / "controle_echelle.md"
MASS_SHARES = (0.7, 0.8, 0.9)
REF_SHARE = 0.8
RATIO_LOW = 0.6
RATIO_HIGH = 1.6
SCALE_LOW = 1.8
SCALE_HIGH = 2.5
MIN_MINOR_SHARE = 0.10
MIN_FLIGHTS = 20
MIN_CELL = 20
SHOWN_PHASES = ("Montée", "Croisière", "Descente")
STATUSES = ("Cohérent", "Échelle suspecte", "Non tranché", "Non vérifiable")


def fmt(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:_.1f}".replace("_", " ").replace(".", ",")
    return f"{value:_}".replace("_", " ")


def dec(value: float | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "n.d."
    return f"{value:.{digits}f}".replace(".", ",")


def kg(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n.d."
    return fmt(round(value))


def ref_col(share: float) -> str:
    return f"ref_{round(share * 100)}"


def cruise_conditions(con) -> pd.DataFrame:
    return con.execute(
        f"""
        SELECT
            aircraft_type,
            count(*) AS n_flights,
            median(alt_ft) AS alt_ft,
            median(gs_kt) AS gs_kt,
            median(kg_per_h) AS observed
        FROM silver.flight_phases
        WHERE phase = 'Croisière' AND reliable
        GROUP BY 1
        HAVING count(*) >= {MIN_FLIGHTS}
        ORDER BY n_flights DESC
        """
    ).df()


def openap_reference(type_code: str, alt_ft: float, speed_kt: float) -> dict[str, float | None]:
    """Débit de croisière OpenAP (kg/h) pour plusieurs hypothèses de masse."""
    result: dict[str, float | None] = {ref_col(s): None for s in MASS_SHARES}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            aircraft = prop.aircraft(type_code.lower())
            fuel_flow = FuelFlow(type_code.lower())
            for share in MASS_SHARES:
                mass = share * aircraft["mtow"]
                kg_per_s = fuel_flow.enroute(mass=mass, tas=speed_kt, alt=alt_ft, vs=0)
                result[ref_col(share)] = float(kg_per_s) * 3600
    except Exception as exc:
        print(f"  Pas de référence OpenAP pour {type_code} : {exc.__class__.__name__}")
    return result


def build_reference(con) -> pd.DataFrame:
    rows = []
    for row in cruise_conditions(con).itertuples(index=False):
        refs = openap_reference(row.aircraft_type, float(row.alt_ft), float(row.gs_kt))
        rows.append(
            {
                "aircraft_type": row.aircraft_type,
                "n_flights": int(row.n_flights),
                "alt_ft": float(row.alt_ft),
                "gs_kt": float(row.gs_kt),
                "observed": float(row.observed),
                **refs,
                "ref_kg_per_h": refs[ref_col(REF_SHARE)],
            }
        )
    reference = pd.DataFrame(rows)
    con.register("reference_df", reference)
    con.execute("CREATE OR REPLACE TABLE silver.cruise_reference AS SELECT * FROM reference_df")
    con.unregister("reference_df")
    return reference


def two_means(values: np.ndarray, iterations: int = 100) -> tuple[float, float, np.ndarray]:
    """Séparation en deux groupes sur une dimension. Renvoie centres et appartenance au haut."""
    low, high = np.quantile(values, [0.25, 0.75])
    for _ in range(iterations):
        upper = np.abs(values - high) < np.abs(values - low)
        if upper.all() or not upper.any():
            break
        new_low, new_high = values[~upper].mean(), values[upper].mean()
        if np.isclose(new_low, low) and np.isclose(new_high, high):
            break
        low, high = new_low, new_high
    upper = np.abs(values - high) < np.abs(values - low)
    return float(low), float(high), upper


def classify(cruise: pd.DataFrame, reference: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    refs = {
        t: (None if pd.isna(r) else float(r))
        for t, r in zip(reference["aircraft_type"], reference["ref_kg_per_h"], strict=True)
    }
    summaries = []
    flights = []
    for type_code, group in cruise.groupby("aircraft_type"):
        rates = group["kg_per_h"].to_numpy(dtype=float)
        ids = group["flight_id"].to_numpy()
        if len(rates) < MIN_FLIGHTS:
            for fid, rate in zip(ids, rates, strict=True):
                flights.append((fid, rate, None, None, "Non vérifiable"))
            continue

        low, high, upper = two_means(np.log(rates))
        center_ratio = float(np.exp(high - low))
        minor_share = float(min(upper.mean(), 1 - upper.mean()))
        two_scales = SCALE_LOW <= center_ratio <= SCALE_HIGH and minor_share >= MIN_MINOR_SHARE
        ref = refs.get(type_code)

        if two_scales and ref is None:
            method = "Deux échelles, pas d'arbitre"
            keep = np.zeros(len(rates), dtype=bool)
            center = None
        elif two_scales:
            keep_upper = abs(high - np.log(ref)) < abs(low - np.log(ref))
            keep = upper if keep_upper else ~upper
            center = float(np.exp(high if keep_upper else low))
            method = "Deux échelles, arbitrage OpenAP"
        else:
            keep = np.ones(len(rates), dtype=bool)
            center = float(np.median(rates))
            method = "Une échelle"

        for fid, rate, kept in zip(ids, rates, keep, strict=True):
            if center is None:
                flights.append((fid, rate, None, None, "Non tranché"))
                continue
            ratio = rate / center
            ok = bool(kept) and RATIO_LOW <= ratio <= RATIO_HIGH
            flights.append((fid, rate, center, ratio, "Cohérent" if ok else "Échelle suspecte"))

        summaries.append(
            {
                "aircraft_type": type_code,
                "n_flights": len(rates),
                "low_center": float(np.exp(low)),
                "high_center": float(np.exp(high)),
                "center_ratio": center_ratio,
                "minor_share": minor_share,
                "two_scales": two_scales,
                "openap_ref": ref,
                "kept_center": center,
                "method": method,
            }
        )

    flight_df = pd.DataFrame(
        flights,
        columns=[
            "flight_id",
            "cruise_kg_per_h",
            "type_center_kg_per_h",
            "ratio_to_center",
            "scale_status",
        ],
    )
    summary_df = pd.DataFrame(summaries).sort_values("n_flights", ascending=False)
    return summary_df, flight_df


def persist(con, summary: pd.DataFrame, flights: pd.DataFrame) -> None:
    con.register("summary_df", summary)
    con.execute("CREATE OR REPLACE TABLE silver.type_scale AS SELECT * FROM summary_df")
    con.unregister("summary_df")

    con.register("scale_df", flights)
    con.execute(
        """
        CREATE OR REPLACE TABLE silver.flight_scale AS
        SELECT
            l.flight_id,
            l.aircraft_type,
            s.cruise_kg_per_h,
            s.type_center_kg_per_h,
            s.ratio_to_center,
            coalesce(s.scale_status, 'Non vérifiable') AS scale_status
        FROM bronze.flightlist l
        LEFT JOIN scale_df s ON s.flight_id = l.flight_id
        WHERE l.split = 'train'
        """
    )
    con.unregister("scale_df")


def reference_section(reference: pd.DataFrame) -> list[str]:
    headers = " | ".join(f"OpenAP {round(s * 100)} % MTOW" for s in MASS_SHARES)
    lines = [
        "## Référence physique OpenAP en croisière (kg/h)",
        "",
        "Conditions : altitude et vitesse sol médianes de la croisière mesurée du type.",
        "",
        f"| Type | Vols | Altitude (ft) | Vitesse sol (kt) | {headers} "
        "| Mesuré (médiane) | Mesuré / référence 80 % |",
        "|---|---:|---:|---:|" + "---:|" * len(MASS_SHARES) + "---:|---:|",
    ]
    agreeing = []
    for row in reference.itertuples(index=False):
        refs = " | ".join(kg(getattr(row, ref_col(s))) for s in MASS_SHARES)
        ratio = row.observed / row.ref_kg_per_h if row.ref_kg_per_h else None
        if ratio is not None and 0.9 <= ratio <= 1.1:
            agreeing.append(row.aircraft_type)
        lines.append(
            f"| {row.aircraft_type} | {fmt(row.n_flights)} | {kg(row.alt_ft)} "
            f"| {kg(row.gs_kt)} | {refs} | {kg(row.observed)} | {dec(ratio)} |"
        )
    lines += [
        "",
        "Types où mesure et référence concordent (rapport entre 0,9 et 1,1) : "
        + (", ".join(agreeing) if agreeing else "aucun")
        + ". Ailleurs, OpenAP sert seulement à arbitrer entre deux échelles, "
        "pas à juger un vol isolé.",
    ]
    return lines


def type_scale_section(summary: pd.DataFrame) -> list[str]:
    lines = [
        "",
        "## Recherche de deux échelles par type",
        "",
        "| Type | Vols | Centre bas (kg/h) | Centre haut (kg/h) | Rapport des centres "
        "| Part du petit groupe | Référence OpenAP | Échelle retenue | Méthode |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary.head(14).itertuples(index=False):
        lines.append(
            f"| {row.aircraft_type} | {fmt(int(row.n_flights))} | {kg(row.low_center)} "
            f"| {kg(row.high_center)} | {dec(row.center_ratio)} "
            f"| {dec(row.minor_share * 100, 1)} % | {kg(row.openap_ref)} "
            f"| {kg(row.kept_center)} | {row.method} |"
        )
    return lines


def status_section(con) -> list[str]:
    columns = ", ".join(f"count(*) FILTER (WHERE scale_status = '{s}')" for s in STATUSES)
    lines = [
        "",
        "## Statut des vols d'entraînement",
        "",
        "| Type | " + " | ".join(STATUSES) + " | Total |",
        "|---|" + "---:|" * (len(STATUSES) + 1),
    ]
    for row in con.execute(
        f"""
        SELECT aircraft_type, {columns}, count(*) AS total
        FROM silver.flight_scale
        GROUP BY 1
        ORDER BY total DESC
        LIMIT 12
        """
    ).fetchall():
        lines.append(f"| {row[0]} | " + " | ".join(fmt(v) for v in row[1:]) + " |")
    return lines


def publishable_section(con) -> list[str]:
    lines = [
        "",
        "## Débit médian par vol et par phase, vols cohérents uniquement (kg/h)",
        "",
        f"Format : médiane (nombre de vols). Cellules de moins de {MIN_CELL} vols "
        "non affichées. Ce sont les seuls chiffres absolus publiables à ce stade.",
        "",
        "| Type | " + " | ".join(SHOWN_PHASES) + " |",
        "|---|" + "---:|" * len(SHOWN_PHASES),
    ]
    types = [
        r[0]
        for r in con.execute(
            "SELECT aircraft_type FROM silver.flight_scale WHERE scale_status = 'Cohérent' "
            "GROUP BY 1 ORDER BY count(*) DESC LIMIT 12"
        ).fetchall()
    ]
    medians = {}
    for type_code in types:
        cells = []
        for phase in SHOWN_PHASES:
            median, n = con.execute(
                """
                SELECT median(p.kg_per_h), count(*)
                FROM silver.flight_phases p
                JOIN silver.flight_scale s ON s.flight_id = p.flight_id
                WHERE s.scale_status = 'Cohérent'
                    AND p.aircraft_type = ? AND p.phase = ?
                    AND p.reliable AND NOT p.outlier
                """,
                [type_code, phase],
            ).fetchone()
            if phase == "Croisière":
                medians[type_code] = median
            cells.append(f"{kg(median)} ({fmt(n)})" if n >= MIN_CELL else "n.d.")
        lines.append(f"| {type_code} | " + " | ".join(cells) + " |")

    if medians.get("A20N") and medians.get("A320"):
        gap = 1 - medians["A20N"] / medians["A320"]
        lines += [
            "",
            f"Sur les vols cohérents, la croisière médiane de l'A20N est inférieure de "
            f"{dec(gap * 100, 1)} % à celle de l'A320.",
        ]
    return lines


def main() -> int:
    con = connect()
    print("Contrôle d'échelle")
    reference = build_reference(con)
    cruise = con.execute(
        "SELECT flight_id, aircraft_type, kg_per_h FROM silver.flight_phases "
        "WHERE phase = 'Croisière' AND reliable"
    ).df()
    summary, flights = classify(cruise, reference)
    persist(con, summary, flights)

    lines = [
        "# Contrôle d'échelle du carburant mesuré (règle R9, version 2)",
        "",
        "Recherche, type par type, de deux populations de vols dont les débits diffèrent "
        "d'un facteur constant. OpenAP (TU Delft) sert d'arbitre entre deux échelles, puis "
        "chaque vol est comparé au centre de son échelle retenue.",
        "",
    ]
    lines += reference_section(reference)
    lines += type_scale_section(summary)
    lines += status_section(con)
    lines += publishable_section(con)

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    print("\n" + "\n".join(lines))
    print(f"\nRapport écrit : {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
