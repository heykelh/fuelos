from pipeline import config


def test_paths_are_inside_project():
    for path in (config.BRONZE_DIR, config.SILVER_DIR, config.GOLD_DIR, config.DUCKDB_PATH):
        assert config.ROOT in path.parents


def test_zenodo_record_id_is_numeric():
    assert config.ZENODO_RECORD_ID.isdigit()


def test_co2_factor_is_icao_standard():
    assert config.CO2_PER_KG_FUEL == 3.16


def test_paris_airports():
    assert set(config.PARIS_AIRPORTS) == {"LFPG", "LFPO"}
