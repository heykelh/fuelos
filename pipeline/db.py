"""Connexion partagée à la base DuckDB de FUELOS."""

from __future__ import annotations

import duckdb

from config import DATA_DIR, DUCKDB_PATH


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Ouvre la base locale avec un dossier temporaire pour les traitements volumineux."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = DATA_DIR / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=read_only)
    con.execute(f"SET temp_directory = '{tmp_dir.as_posix()}'")
    con.execute("SET preserve_insertion_order = false")
    return con
