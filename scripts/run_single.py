#!/usr/bin/env python3
"""
Do a single map build from a json file with locations.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from cm_modular.pipeline import Pipeline, PipelineConfig

def parse_args():
    p = argparse.ArgumentParser(description="Build cluster map with angle-biased path.")
    p.add_argument("file", type=str, nargs='+', help="Path(s) to JSON file(s) with 'locations'.")
    p.add_argument("--out", type=str, default=None, help="Output HTML path.")
    p.add_argument("--city", type=str, default=None, help="City preset name (overrides bbox if supplied).")
    p.add_argument("--lat-min", type=float, default=53.3, help="Minimum latitude (default: %(default)s)")
    p.add_argument("--lat-max", type=float, default=53.8, help="Maximum latitude (default: %(default)s)")
    p.add_argument("--lon-min", type=float, default=9.6, help="Minimum longitude (default: %(default)s)")
    p.add_argument("--lon-max", type=float, default=10.35, help="Maximum longitude (default: %(default)s)")
    p.add_argument("--k", type=int, default=6, help="Number of clusters (default: %(default)s)")
    p.add_argument("--n-sigmas", type=float, default=3.0, help="Sigma multiplier for bounds (default: %(default)s)")
    p.add_argument("--L0", type=float, default=50.0, help="Base length parameter (default: %(default)s)")
    p.add_argument("--penalty-factor", type=float, default=3.0, help="Penalty factor (default: %(default)s)")
    p.add_argument("--angle-bias", type=float, default=8.0, help="Meters per radian (default: %(default)s)")
    p.add_argument("--step-penalty", type=float, default=5.0, help="Meters per edge (default: %(default)s)")
    p.add_argument("--min-edge-cost", type=float, default=15.0, help="Minimum meters per edge (default: %(default)s)")
    p.add_argument("--bounds-expand", type=float, default=2.0, help="Bounds expansion factor (default: %(default)s)")
    p.add_argument("--plot-graph", action="store_true", help="Enable graph output (plot/draw graph).")
    p.add_argument("--clustering-timespan", type=float, default=None, help="Timespan (seconds) for clustering.")
    p.add_argument("--path-timespan", type=float, default=None, help="Timespan (seconds) for path length (<= clustering timespan).")
    return p.parse_args()

def main():
    a = parse_args()
    cfg = PipelineConfig(
        city=a.city,
        lat_min=a.lat_min, lat_max=a.lat_max, lon_min=a.lon_min, lon_max=a.lon_max,
        k=a.k, n_sigmas=a.n_sigmas,
        L0=a.L0, penalty_factor=a.penalty_factor,
        angle_bias_m_per_rad=a.angle_bias, step_penalty_m=a.step_penalty, min_edge_cost_m=a.min_edge_cost,
        bounds_expand=a.bounds_expand,
        plot_graph=a.plot_graph, graph_cost_mode='adj', graph_out=None,
        clustering_timespan_s=a.clustering_timespan,
        path_timespan_s=a.path_timespan,
    )
    # Expand wildcards in file arguments
    expanded_files = []
    for fpattern in a.file:
        if any(c in fpattern for c in ['*', '?', '[']):
            expanded_files.extend([str(p) for p in Path().glob(fpattern)])
        else:
            expanded_files.append(fpattern)
    if not expanded_files:
        raise FileNotFoundError("No files matched the given pattern(s).")
    pipe = Pipeline(cfg)
    pipe.add_files(expanded_files)
    m, out = pipe.run(a.out)
    print(f"Wrote: {out}")

if __name__ == "__main__":
    main()
