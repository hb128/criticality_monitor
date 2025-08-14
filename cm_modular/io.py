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
        Returns a DataFrame with columns ['id', 'lat', 'lon'] where lat/lon are in degrees.

        Parameters
        ----------
        file_path : str | Path
            Path to the JSON file.

        Returns
        -------
        pd.DataFrame
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        rows = []
        for _id, o in (data.get("locations", {}) or {}).items():
            lat = o.get("latitude"); lon = o.get("longitude")
            if lat is None or lon is None:
                continue
            rows.append((_id, float(lat)/1e6, float(lon)/1e6))
        return pd.DataFrame(rows, columns=["id", "lat", "lon"])
