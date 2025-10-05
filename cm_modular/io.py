from __future__ import annotations
from pathlib import Path
import json
import pandas as pd

class DataLoader:
    """Load and prepare location data from the JSON format used by the project."""
    @staticmethod
    def load_locations_json(file_path: str | Path) -> pd.DataFrame:
        """Load a JSON file with a top-level `locations` dict of objects.

        Each object is expected to include integer micro-degree `latitude` and `longitude` fields.
        Returns a DataFrame with columns ['id', 'lat', 'lon', 'timestamp'] where lat/lon are in degrees.

        Parameters
        ----------
        file_path : str | Path
            Path to the JSON file.

        Returns
        -------
        pd.DataFrame
        """
        # print(f"Loading locations from {file_path}")
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        rows = []
        for _id, o in (data.get("locations", {}) or {}).items():
            timestamp = o.get("timestamp")
            lat = o.get("latitude"); lon = o.get("longitude")
            if lat is None or lon is None:
                continue
            rows.append((_id, float(lat)/1e6, float(lon)/1e6, timestamp))
        return pd.DataFrame(rows, columns=["id", "lat", "lon", "timestamp"])

    @staticmethod
    def load_multiple_locations_json(file_paths: list[str | Path]) -> pd.DataFrame:
        """
        Load multiple JSON files and aggregate location data.
        Returns a DataFrame with columns ['id', 'lat', 'lon', 'timestamp'].
        Each row is a single observation for an ID at a timestamp.

        Parameters
        ----------
        file_paths : list[str | Path]
            List of paths to JSON files.

        Returns
        -------
        pd.DataFrame
        """
        dfs = [DataLoader.load_locations_json(fp) for fp in file_paths]
        if not dfs:
            return pd.DataFrame(columns=["id", "lat", "lon", "timestamp"])
        # print(f"Loaded {len(dfs)} files with total {sum(len(df) for df in dfs)} records. Merge them now.")
        df = pd.concat(dfs, ignore_index=True)
        # Optionally sort by id and timestamp for time series analysis
        df = df.sort_values(["id", "timestamp"]).reset_index(drop=True)
        # print(f"Merged DataFrame has {len(df)} records.")
        return df
