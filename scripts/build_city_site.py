#!/usr/bin/env python3
"""Convenience wrapper: run batch_build then build_site for a city.

Example:
  python -m scripts.build_city_site cm_logs/20220624 --city zurich --workers 4 --no-copy-maps

This expands to roughly:
  python -m scripts.batch_build cm_logs/20220624 --city zurich --outdir site/zurich/maps --workers 4
  python -m scripts.build_site site/zurich/maps/distances.csv --outdir site/zurich --no-copy-maps

Options let you override defaults similarly to the underlying scripts.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
from typing import List

# Re‑use existing functions from batch_build / build_site
try:
    from scripts import batch_build as bb  # type: ignore
except ImportError:
    import batch_build as bb  # fallback when run as plain script

try:
    from scripts.build_site import build_site  # type: ignore
except ImportError:
    from build_site import build_site  # fallback

from cm_modular.pipeline import PipelineConfig


def parse_args():
    p = argparse.ArgumentParser(description="Run batch_build + build_site in one step.")
    p.add_argument("indir", help="Input directory containing JSON/.txt location files")
    p.add_argument("--city", type=str, default=None, help="City preset name (overrides bbox).")
    p.add_argument("--site-out", type=str, default=None, help="Base site output directory (default: site/<city> or site)")
    p.add_argument("--maps-subdir", default="maps", help="Subdirectory under site-out for individual map HTML (default: maps)")
    p.add_argument("--patterns", nargs="+", default=["*.txt", "*.json"], help="Glob patterns to include (default: *.txt *.json)")
    p.add_argument("--workers", type=int, default=1, help="Parallel workers for batch build (default: 1)")
    # Pipeline overrides (mirrors batch_build / build_map)
    p.add_argument("--lat-min", type=float, default=53.3)
    p.add_argument("--lat-max", type=float, default=53.8)
    p.add_argument("--lon-min", type=float, default=9.6)
    p.add_argument("--lon-max", type=float, default=10.35)
    p.add_argument("--k", type=int, default=6)
    p.add_argument("--n-sigmas", type=float, default=3.0)
    p.add_argument("--L0", type=float, default=50.0)
    p.add_argument("--penalty-factor", type=float, default=3.0)
    p.add_argument("--angle-bias", type=float, default=8.0)
    p.add_argument("--step-penalty", type=float, default=5.0)
    p.add_argument("--min-edge-cost", type=float, default=15.0)
    p.add_argument("--bounds-expand", type=float, default=2.0)
    # Site build options
    p.add_argument("--x", default="t", help="X column for chart (default: t)")
    p.add_argument("--y", nargs="+", default=["length_m"], help="Y column(s) (default: length_m)")
    p.add_argument("--style", choices=["line", "scatter"], default="line")
    p.add_argument("--title", default=None, help="Optional site title")
    p.add_argument("--no-copy-maps", dest="copy_maps", action="store_false", help="Do not copy map HTML files into site")
    p.add_argument("--query", default=None, help="Optional pandas query filter for CSV rows")
    return p.parse_args()


def main():
    a = parse_args()
    indir = Path(a.indir).expanduser().resolve()
    if not indir.exists() or not indir.is_dir():
        print(f"Input directory not found: {indir}", file=sys.stderr)
        sys.exit(2)

    # Derive site base directory
    if a.site_out:
        site_base = Path(a.site_out).expanduser().resolve()
    else:
        site_base = Path("site") / (a.city.lower() if a.city else "")
        site_base = site_base.resolve()

    maps_dir = site_base / a.maps_subdir
    maps_dir.mkdir(parents=True, exist_ok=True)

    # Configure pipeline
    cfg = PipelineConfig(
        city=a.city,
        lat_min=a.lat_min, lat_max=a.lat_max, lon_min=a.lon_min, lon_max=a.lon_max,
        k=a.k, n_sigmas=a.n_sigmas,
        L0=a.L0, penalty_factor=a.penalty_factor,
        angle_bias_m_per_rad=a.angle_bias, step_penalty_m=a.step_penalty, min_edge_cost_m=a.min_edge_cost,
        bounds_expand=a.bounds_expand,
    )

    # Run batch via shared function
    try:
        csv_path = bb.run_batch(indir, maps_dir, a.patterns, cfg, workers=a.workers)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # Build site
    build_site(
        csv_path=csv_path,
        outdir=site_base,
        x_col=a.x,
        y_cols=a.y,
        style=a.style,
        title=a.title or (f"{a.city} critical length" if a.city else None),
        copy_maps=a.copy_maps,
        maps_subdir=a.maps_subdir,
        query=a.query,
    )

    print(f"Done. Open: {site_base / 'index.html'}")


if __name__ == "__main__":
    main()
