#!/usr/bin/env python3
"""
Plot columns from JSON state files.

Examples
--------
# Basic: plot length_m over (parsed) timestamp from the 'file' path
python plot_metrics.py results.json

# Choose columns
python plot_metrics.py results.json --y length_m n_filtered largest_comp_size

# Pick a different x-axis (index) and save to PNG
python plot_metrics.py results.json --x index --out out.png

# Filter rows by a simple query (pandas query syntax)
python plot_metrics.py results.json --query "connection_radius_m == 200 and L0_m == 50"
"""
import argparse
import re
import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


STAMP_RE = re.compile(r"(?P<stamp>\d{8}_\d{6})")  # e.g., 20220624_202509


def parse_timestamp_from_path(s: str):
    """Extract a timestamp like YYYYMMDD_HHMMSS from any path-like string."""
    if not isinstance(s, str):
        return pd.NaT
    m = STAMP_RE.search(s)
    if not m:
        return pd.NaT
    return pd.to_datetime(m.group("stamp"), format="%Y%m%d_%H%M%S")


def load_data(data_path: Path) -> pd.DataFrame:
    """Load data from JSON state file."""
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    if not results:
        raise ValueError(f"No results found in JSON state file: {data_path}")
    
    return pd.DataFrame(results)


def ensure_time_column(df: pd.DataFrame) -> pd.DataFrame:
    """Create column 't' by parsing from 'file' (falls back to 'html')."""
    t = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    for col in ("file", "html"):
        if col in df.columns:
            parsed = df[col].map(parse_timestamp_from_path)
            t = parsed.where(parsed.notna(), t)
    if t.notna().any():
        df = df.copy()
        df["t"] = t
    return df


def main():
    p = argparse.ArgumentParser(
        description="Plot columns from JSON state files."
    )
    p.add_argument("data", help="Path to the JSON state file.")
    p.add_argument(
        "--x",
        default="t",
        help="X column to plot (default: 't' parsed from paths). Use 'index' to use row index.",
    )
    p.add_argument(
        "--y",
        nargs="+",
        default=["length_m"],
        help="One or more Y columns to plot (default: length_m).",
    )
    p.add_argument(
        "--query",
        default=None,
        help='Optional pandas query to filter rows, e.g. "connection_radius_m == 200".',
    )
    p.add_argument("--title", default=None, help="Figure title.")
    p.add_argument("--out", default=None, help="Optional output filename (PNG, PDF, SVG).")
    p.add_argument(
        "--style",
        choices=["line", "scatter"],
        default="line",
        help="Plot style for Y series (default: line).",
    )
    p.add_argument(
        "--figsize",
        type=float,
        nargs=2,
        metavar=("W", "H"),
        default=(9, 4.5),
        help="Figure size in inches (default: 9 4.5).",
    )
    args = p.parse_args()

    # Load
    data_path = Path(args.data).expanduser().resolve()
    df = load_data(data_path)

    # Enrich with parsed time
    df = ensure_time_column(df)

    # Optional filter
    if args.query:
        df = df.query(args.query)

    # Choose x
    if args.x == "index":
        x = df.index
        x_label = "index"
    else:
        if args.x not in df.columns:
            # If default 't' is requested but missing, fall back gracefully
            if args.x == "t":
                df = ensure_time_column(df)
            if args.x not in df.columns:
                raise SystemExit(f"X column '{args.x}' not found. Available: {list(df.columns)}")
        x = df[args.x]
        x_label = args.x

    # Begin plot
    plt.figure(figsize=tuple(args.figsize))
    for ycol in args.y:
        if ycol not in df.columns:
            print(f"Warning: y column '{ycol}' not found; skipping.")
            continue
        if args.style == "line":
            plt.plot(x, df[ycol], label=ycol)
        else:
            plt.scatter(x, df[ycol], label=ycol)
    plt.grid(True, alpha=0.3)
    plt.xlabel(x_label)
    plt.ylabel(", ".join(args.y))
    if args.title:
        plt.title(args.title)
    else:
        plt.title(Path(args.data).name)
    if any(ycol in df.columns for ycol in args.y):
        plt.legend()

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(args.out, dpi=150)
        print(f"Saved plot to {args.out}")
    else:
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
