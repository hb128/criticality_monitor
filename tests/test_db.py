import duckdb
import pandas as pd
import datetime as dt
import pytest
from cm_modular.db import init_db, observations_from_api_payload, insert_observations

SAMPLE_PAYLOAD = {
    "locations": {
        "abc": {"latitude": 53_550_000, "longitude": 10_010_000, "timestamp": 1741028671},
        "def": {"latitude": 53_560_000, "longitude": 10_020_000, "timestamp": 1741028672},
    }
}

SAMPLE_INGESTED_AT = dt.datetime(2020, 2, 1, 12, 13, tzinfo=dt.timezone.utc)


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    init_db(c)
    return c


def test_init_db_creates_observations_table(conn):
    tables = conn.execute("SHOW TABLES").fetchdf()
    assert "observations" in tables["name"].values


def test_observations_has_at_least_expected_columns(conn):
    cols = conn.execute("DESCRIBE observations").fetchdf()
    col_names = cols["column_name"].tolist()
    assert {"id", "lat", "lon", "timestamp", "ingested_at", "source_file", "city"} <= set(col_names)


def test_insert_observations_writes_one_row_per_input_point(conn):
    df = observations_from_api_payload(SAMPLE_PAYLOAD, city="Hamburg", source_file="test.txt", ingested_at=SAMPLE_INGESTED_AT)
    n = insert_observations(conn, df)
    result = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert n == 2
    assert result == 2


def test_insert_observations_adds_metadata_city_source_file_ingested_at(conn):
    df = observations_from_api_payload(SAMPLE_PAYLOAD, city="Hamburg", source_file="test.txt", ingested_at=SAMPLE_INGESTED_AT)
    insert_observations(conn, df)
    row = conn.execute("SELECT city, source_file, ingested_at FROM observations LIMIT 1").fetchone()
    assert row[0] == "Hamburg"
    assert row[1] == "test.txt"
    assert row[2] == SAMPLE_INGESTED_AT


def test_insert_observations_two_batches_both_persist(conn):
    df = observations_from_api_payload(SAMPLE_PAYLOAD, city="Hamburg", source_file="test.txt", ingested_at=SAMPLE_INGESTED_AT)
    insert_observations(conn, df)
    later = SAMPLE_INGESTED_AT + dt.timedelta(seconds=30)
    df2 = observations_from_api_payload(SAMPLE_PAYLOAD, city="Hamburg", source_file="test.txt", ingested_at=later)
    insert_observations(conn, df2)
    result = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert result == 4  # 2 IDs × 2 ingestion times, both valid observations