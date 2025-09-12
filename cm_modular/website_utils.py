"""
Utility functions for website building.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Timestamp parsing utilities
STAMP_RE = re.compile(r"(?P<stamp>\d{8}_\d{6})")


def parse_timestamp_from_path(s: str):
    """Parse timestamp from file path."""
    if not isinstance(s, str):
        return pd.NaT
    m = STAMP_RE.search(s)
    if not m:
        return pd.NaT
    return pd.to_datetime(m.group("stamp"), format="%Y%m%d_%H%M%S")


def ensure_time_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has a time column parsed from file paths."""
    t = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    for col in ("file", "html"):
        if col in df.columns:
            parsed = df[col].map(parse_timestamp_from_path)
            t = parsed.where(parsed.notna(), t)
    if t.notna().any():
        df = df.copy()
        df["t"] = t
    return df


def make_safe_filename(base: str) -> str:
    """Create a safe filename from a base string."""
    return re.sub(r'[<>:"/\\|?*]', '_', base)
