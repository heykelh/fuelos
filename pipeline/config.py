"""Configuration centrale de FUELOS : chemins, sources et constantes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Architecture médaillon
DATA_DIR = ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

# Sources Bronze
BRONZE_PRC_DIR = BRONZE_DIR / "prc2025"
BRONZE_EUROCONTROL_DIR = BRONZE_DIR / "eurocontrol"
BRONZE_ICAO_DIR = BRONZE_DIR / "icao_eedb"

# Base analytique locale
DUCKDB_PATH = DATA_DIR / "fuelos.duckdb"

# Export vers le site
WEB_DATA_DIR = ROOT / "web" / "public" / "data"

# PRC Data Challenge 2025 (Eurocontrol, OpenSky Network, TU Delft)
# DOI : 10.5281/zenodo.19184661
ZENODO_RECORD_ID = "19184661"

# Facteur OACI : kg de CO2 émis par kg de carburant brûlé
CO2_PER_KG_FUEL = 3.16

# Aéroports du hub parisien
PARIS_AIRPORTS = ("LFPG", "LFPO")


def ensure_dirs() -> None:
    """Crée l'arborescence de données si elle n'existe pas."""
    for path in (
        BRONZE_PRC_DIR,
        BRONZE_EUROCONTROL_DIR,
        BRONZE_ICAO_DIR,
        SILVER_DIR,
        GOLD_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
