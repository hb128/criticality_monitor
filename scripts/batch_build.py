#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable

from cm_modular.pipeline import PipelineConfig
from cm_modular.io import DataLoader
from cm_modular.geo import GeoUtils
from cm_modular.filtering import RobustKNNFilter, DataFilter
from cm_modular.graphing import GraphBuilder
from cm_modular.clustering import Clusterer
from cm_modular.routing import AngleBiasedRouter
from cm_modular.mapping import MapBuilder

def iter_files(indir: Path, patterns: list[str]) -> Iterable[Path]:
    """Yield files in *indir* matching any of the glob *patterns* (non-recursive)."""
    seen = set()
    for pat in patterns:
        for p in indir.glob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield p

def build_map_and_metrics(file_path: Path, cfg: PipelineConfig, out_html: Path):
    """Run the same pipeline steps as Pipeline.run, but also return metrics."""
    # load & bbox filter
    df = DataLoader.load_locations_json(file_path)
    hh = DataFilter.bbox(df, cfg.lat_min, cfg.lat_max, cfg.lon_min, cfg.lon_max)

    # geometry + KNN filter
    x, y = GeoUtils.deg2meters(hh["lat"].values, hh["lon"].values)
    D = GeoUtils.pairwise_xy(x, y)
    keep, k_med = RobustKNNFilter.keep_by_knn(D, k=cfg.k, n_sigmas=cfg.n_sigmas)
    hh = hh.copy()
    hh["keep"] = keep
    filtered = hh[hh["keep"]].copy().reset_index(drop=True)
    outliers = hh[~hh["keep"]].copy().reset_index(drop=True)

    # graph on filtered
    x_f, y_f = GeoUtils.deg2meters(filtered["lat"].values, filtered["lon"].values)
    D_f = GeoUtils.pairwise_xy(x_f, y_f)
    adj, radius_m = GraphBuilder.build_graph(D_f, k_med, L0=cfg.L0, penalty_factor=cfg.penalty_factor)

    # cluster ids
    comps, sizes, order, cluster_id = Clusterer.assign_from_components(adj)
    filtered["cluster"] = cluster_id

    # diameter path on largest component using angle-biased metric
    path_indices = []
    start_idx = end_idx = None
    length_m = 0.0
    if order:
        main = comps[order[0]]
        if len(main) >= 2:
            router = AngleBiasedRouter(x_f, y_f,
                                       angle_bias_m_per_rad=cfg.angle_bias_m_per_rad,
                                       step_penalty_m=cfg.step_penalty_m,
                                       min_edge_cost_m=cfg.min_edge_cost_m)
            s0 = main[0]
            dist0, prev0, bestprev0 = router.dijkstra(adj, s0)
            a = max(main, key=lambda i: dist0[i])
            dist_a, prev_a, bestprev_a = router.dijkstra(adj, a)
            b = max(main, key=lambda i: dist_a[i])
            path_indices = router.reconstruct_path(prev_a, b, bestprev_a[b])
            start_idx, end_idx = a, b
            length_m = router.path_true_length_m(D_f, path_indices)

    # map
    m = MapBuilder().build(
        filtered=filtered,
        outliers=outliers,
        cluster_sizes=sizes,
        order=order,
        path_indices=path_indices,
        start_idx=start_idx,
        end_idx=end_idx,
        length_m=length_m,
        angle_bias_m_per_rad=cfg.angle_bias_m_per_rad,
        bounds_expand=cfg.bounds_expand,
    )
    m.save(str(out_html))

    # metrics summary
    metrics = {
        "file": str(file_path),
        "html": str(out_html),
        "n_points": int(len(df)),
        "n_bbox": int(len(hh)),
        "n_filtered": int(len(filtered)),
        "largest_comp_size": int(sizes[order[0]]) if order else 0,
        "connection_radius_m": float(radius_m),
        "length_m": float(length_m),
        "angle_bias_m_per_rad": float(cfg.angle_bias_m_per_rad),
        "L0_m": float(cfg.L0),
        "penalty_factor": float(cfg.penalty_factor),
    }
    return metrics

def parse_args():
    p = argparse.ArgumentParser(description="Batch-build cluster maps and export distances CSV.")
    p.add_argument("indir", type=str, help="Directory containing input files (JSON-within-.txt is fine)." )
    p.add_argument("--outdir", type=str, default=None, help="Directory to write HTML maps (default: <indir>/maps).")
    p.add_argument("--csv", type=str, default=None, help="Path to write CSV summary (default: <outdir>/distances.csv)." )
    p.add_argument("--pattern", action="append", default=["*.txt", "*.json"], help="Glob pattern(s) to include (can repeat). Default: *.txt, *.json" )
    # Config overrides
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
    return p.parse_args()

def main():
    a = parse_args()
    indir = Path(a.indir).expanduser().resolve()
    if not indir.exists() or not indir.is_dir():
        print(f"Input directory not found: {indir}", file=sys.stderr)
        sys.exit(2)

    outdir = Path(a.outdir).expanduser().resolve() if a.outdir else (indir / "maps")
    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = Path(a.csv).expanduser().resolve() if a.csv else (outdir / "distances.csv")

    cfg = PipelineConfig(
        lat_min=a.lat_min, lat_max=a.lat_max, lon_min=a.lon_min, lon_max=a.lon_max,
        k=a.k, n_sigmas=a.n_sigmas,
        L0=a.L0, penalty_factor=a.penalty_factor,
        angle_bias_m_per_rad=a.angle_bias, step_penalty_m=a.step_penalty, min_edge_cost_m=a.min_edge_cost,
        bounds_expand=a.bounds_expand,
    )

    files = sorted(iter_files(indir, a.pattern))
    if not files:
        print(f"No files matched in {indir} with patterns {a.pattern}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for i, f in enumerate(files, 1):
        try:
            out_html = outdir / (f.stem + "_clusters_with_path_angle.html")
            print(f"[{i}/{len(files)}] Processing {f.name} -> {out_html.name}")
            metrics = build_map_and_metrics(f, cfg, out_html)
            rows.append(metrics)
        except Exception as e:
            print(f"ERROR processing {f}: {e}", file=sys.stderr)
            rows.append({
                "file": str(f),
                "html": "",
                "n_points": 0,
                "n_bbox": 0,
                "n_filtered": 0,
                "largest_comp_size": 0,
                "connection_radius_m": 0.0,
                "length_m": 0.0,
                "angle_bias_m_per_rad": cfg.angle_bias_m_per_rad,
                "L0_m": cfg.L0,
                "penalty_factor": cfg.penalty_factor,
                "error": str(e),
            })

    # Write CSV
    fieldnames = ["file", "html", "n_points", "n_bbox", "n_filtered", "largest_comp_size",
                  "connection_radius_m", "length_m", "angle_bias_m_per_rad", "L0_m", "penalty_factor", "error"]
    # ensure 'error' column exists even on successful rows
    for r in rows:
        r.setdefault("error", "")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote CSV: {csv_path}")
    print(f"Wrote {len([r for r in rows if not r['error']])} HTML maps to: {outdir}")

if __name__ == "__main__":
    main()
