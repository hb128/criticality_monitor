#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from cm_modular.pipeline import Pipeline, PipelineConfig

def parse_args():
    p = argparse.ArgumentParser(description="Build cluster map with angle-biased path.")
    p.add_argument("file", type=str, help="Path to JSON with 'locations'.")
    p.add_argument("--out", type=str, default=None, help="Output HTML path.")
    p.add_argument("--lat-min", type=float, default=53.3)
    p.add_argument("--lat-max", type=float, default=53.8)
    p.add_argument("--lon-min", type=float, default=9.6)
    p.add_argument("--lon-max", type=float, default=10.35)
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--n-sigmas", type=float, default=3.0)
    p.add_argument("--L0", type=float, default=50.0)
    p.add_argument("--penalty-factor", type=float, default=3.0)
    p.add_argument("--angle-bias", type=float, default=8.0, help="meters per radian")
    p.add_argument("--step-penalty", type=float, default=5.0, help="meters per edge")
    p.add_argument("--min-edge-cost", type=float, default=15.0, help="meters floor per edge")
    p.add_argument("--bounds-expand", type=float, default=2.0)
    p.add_argument("--plot-graph", action="store_true", help="Enable graph output (plot/draw graph).")
    return p.parse_args()

def main():
    a = parse_args()
    cfg = PipelineConfig(
        lat_min=a.lat_min, lat_max=a.lat_max, lon_min=a.lon_min, lon_max=a.lon_max,
        k=a.k, n_sigmas=a.n_sigmas,
        L0=a.L0, penalty_factor=a.penalty_factor,
        angle_bias_m_per_rad=a.angle_bias, step_penalty_m=a.step_penalty, min_edge_cost_m=a.min_edge_cost,
        bounds_expand=a.bounds_expand,
        plot_graph=a.plot_graph, graph_cost_mode='adj', graph_out=None,
    )
    pipe = Pipeline(cfg)
    m, out = pipe.run(a.file, a.out)
    print(f"Wrote: {out}" )

if __name__ == "__main__":
    main()
