#!/usr/bin/env python3
"""
Better script name suggestion: build_city_website.py

Convenience wrapper: run batch_build then build_enhanced_site for a city.

Example:
    python -m scripts.build_city_website cm_logs/20220624 --city zurich --workers 4 --no-copy-maps

This expands to roughly:
    python -m scripts.batch_build cm_logs/20220624 --city zurich --outdir site/zurich/maps --workers 4
    python -m scripts.build_enhanced_site site/zurich/maps/results.json --outdir site/zurich --no-copy-maps

Options let you override defaults similarly to the underlying scripts.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
from typing import List

# Re‑use existing functions from batch_build / build_site
try:
    from scripts import run_batch as bb  # type: ignore
except ImportError:
    import scripts.run_batch as bb  # fallback when run as plain script

try:
    from scripts.build_enhanced_site import build_enhanced_site  # type: ignore
except ImportError:
    from build_enhanced_site import build_enhanced_site  # fallback

from cm_modular.pipeline import PipelineConfig


def parse_args():
    p = argparse.ArgumentParser(description="Run batch_build + build_enhanced_site in one step.")
    p.add_argument("indir", help="Input directory containing JSON/.txt location files")
    p.add_argument("--city", type=str, default="hamburg", help="City preset name (overrides bbox).")
    p.add_argument("--site-out", type=str, default=None, help="Base site output directory (default: site/<city> or site).")
    p.add_argument("--patterns", nargs="+", default=["*.txt", "*.json"], help="Glob patterns to include. Default: %(default)s")
    p.add_argument("--workers", type=int, default=1, help="Parallel workers for batch build. Default: %(default)s")
    # Pipeline overrides (mirrors batch_build / build_map)
    p.add_argument("--lat-min", type=float, default=53.3, help="Minimum latitude. Default: %(default)s")
    p.add_argument("--lat-max", type=float, default=53.8, help="Maximum latitude. Default: %(default)s")
    p.add_argument("--lon-min", type=float, default=9.6, help="Minimum longitude. Default: %(default)s")
    p.add_argument("--lon-max", type=float, default=10.35, help="Maximum longitude. Default: %(default)s")
    p.add_argument("--k", type=int, default=6, help="Number of clusters (k). Default: %(default)s")
    p.add_argument("--n-sigmas", type=float, default=3.0, help="Sigma threshold. Default: %(default)s")
    p.add_argument("--L0", type=float, default=50.0, help="L0 parameter. Default: %(default)s")
    p.add_argument("--penalty-factor", type=float, default=3.0, help="Penalty factor. Default: %(default)s")
    p.add_argument("--angle-bias", type=float, default=8.0, help="Angle bias. Default: %(default)s")
    p.add_argument("--step-penalty", type=float, default=5.0, help="Step penalty. Default: %(default)s")
    p.add_argument("--min-edge-cost", type=float, default=15.0, help="Minimum edge cost. Default: %(default)s")
    p.add_argument("--bounds-expand", type=float, default=2.0, help="Bounds expand factor. Default: %(default)s")
    p.add_argument("--recalculate", action="store_true", help="Recalculate all data.")
    p.add_argument("--max-minutes-plot", type=int, default=120, help="Number of minutes to show in the time series plot (default: %(default)s)")
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
        site_base = Path("data/sites")
        site_base = site_base.resolve()
    maps_dir = site_base / (a.city.lower() if a.city else "")
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
        state_path = bb.run_batch(indir, maps_dir, a.patterns, cfg, workers=a.workers, incremental=not a.recalculate)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # Build site
    build_enhanced_site(
        data_path=state_path,
        outdir=site_base,
        city=a.city or "Criticality Monitor",
        html_name=f"{a.city.lower()}.html",
        max_minutes_plot=a.max_minutes_plot
    )

    print(f"Done. Open: {site_base / f'{a.city.lower()}.html'}")


if __name__ == "__main__":
    main()
