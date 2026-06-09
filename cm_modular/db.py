import duckdb
import pandas as pd
from datetime import datetime


def connect(db_path: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(db_path)


def init_db(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id TEXT NOT NULL,
            lat DOUBLE NOT NULL,
            lon DOUBLE NOT NULL,
            timestamp DOUBLE,
            ingested_at TIMESTAMPTZ NOT NULL,
            source_file TEXT,
            city TEXT,
            PRIMARY KEY (id, ingested_at)
        )
    """)


def observations_from_api_payload(
    payload: dict,
    *,
    city: str | None,
    source_file: str | None,
    ingested_at: datetime,
) -> pd.DataFrame:
    rows = []
    for obs_id, entry in payload.get("locations", {}).items():
        rows.append({
            "id":          str(obs_id),
            "lat":         entry["latitude"] / 1_000_000,
            "lon":         entry["longitude"] / 1_000_000,
            "timestamp":   entry.get("timestamp"),
            "ingested_at": ingested_at,
            "source_file": source_file,
            "city":        city,
        })
    return pd.DataFrame(rows, columns=["id", "lat", "lon", "timestamp", "ingested_at", "source_file", "city"])


def insert_observations(conn: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    conn.execute("INSERT INTO observations BY NAME SELECT * FROM df")
    return len(df)