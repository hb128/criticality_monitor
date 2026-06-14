#!/usr/bin/env python3
"""
Convert historical .txt JSON log files into the observations DuckDB database.
Usage: python convert_to_database.py <log_dir> <db_path> [--city CITY]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from cm_modular.db import connect, init_db, observations_from_api_payload, insert_observations
from cm_modular.website_utils import parse_timestamp_from_path


def convert_folder(log_dir: str, db_path: str) -> None:
    files = sorted(Path(log_dir).glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No .txt files found in {log_dir}")

    conn = connect(db_path)
    init_db(conn)

    total = 0
    for path in files:
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"Skipping {path.name}: {e}")
            continue

        ingested_at = parse_timestamp_from_path(str(path))
        if ingested_at is None or ingested_at is pd.NaT:
            print(f"Skipping {path.name}: could not parse timestamp from filename")
            continue

        ingested_at = ingested_at.to_pydatetime().replace(tzinfo=timezone.utc)

        df = observations_from_api_payload(
            payload,
            ingested_at=ingested_at,
        )
        n = insert_observations(conn, df)
        total += n
        print(f"{path.name}: {n} rows")

    print(f"\nDone. {len(files)} files → {total} rows inserted into {db_path}")


def main():
    parser = argparse.ArgumentParser(description="Convert .txt log files to DuckDB observations table")
    parser.add_argument("log_dir", help="Directory containing .txt log files")
    parser.add_argument("db_path", help="Path to DuckDB database file (created if absent)")
    args = parser.parse_args()
    convert_folder(args.log_dir, args.db_path)


if __name__ == "__main__":
    main()