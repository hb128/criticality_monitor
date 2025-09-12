#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import sys
import os
import concurrent.futures
from pathlib import Path
from typing import Iterable

from cm_modular.pipeline import PipelineConfig, Pipeline

def iter_files(indir: Path, patterns: list[str]) -> Iterable[Path]:
    """Yield files in *indir* matching any of the glob *patterns* (non-recursive)."""
    seen = set()
    for pat in patterns:
        for p in indir.glob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield p

def build_map_and_metrics(file_path: Path, cfg: PipelineConfig, out_html: Path):
    """Use Pipeline.run_with_metrics to produce the map and metrics."""
    pipeline = Pipeline(cfg)
    _, html_written, metrics = pipeline.run_with_metrics(file_path, out_html)
    return metrics

def run_batch(
    indir: Path,
    outdir: Path,
    patterns: list[str],
    cfg: PipelineConfig,
    *,
    workers: int = 1,
    csv_path: Path | None = None,
) -> Path:
    """Run batch processing of files and write distances CSV.

    Parameters
    ----------
    indir : Path
        Input directory containing raw location files.
    outdir : Path
        Directory where individual map HTML files will be written.
    patterns : list[str]
        Glob patterns to include (non-recursive) e.g. ["*.txt", "*.json"].
    cfg : PipelineConfig
        Pipeline configuration.
    workers : int, default 1
        Parallel workers (<=1 means serial).
    csv_path : Path | None
        Explicit CSV output path. If None, uses outdir / "distances.csv".

    Returns
    -------
    Path
        Path to written CSV file.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    if csv_path is None:
        csv_path = outdir / "distances.csv"

    files = sorted(iter_files(indir, patterns))
    if not files:
        raise FileNotFoundError(f"No files matched in {indir} with patterns {patterns}")

    rows: list[dict] = []
    workers_eff = workers if workers and workers > 1 else 1

    if workers_eff == 1:
        for i, f in enumerate(files, 1):
            try:
                out_html = outdir / (f.stem + ".html")
                print(f"[{i}/{len(files)}] Processing {f.name} -> {out_html.name}")
                metrics = build_map_and_metrics(f, cfg, out_html)
                rows.append(metrics)
            except Exception as e:  # noqa: BLE001
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
    else:
        max_workers = workers_eff if workers_eff > 0 else os.cpu_count() or 1
        print(f"Running with {max_workers} workers")
        futures: dict[concurrent.futures.Future, tuple[int, Path, Path]] = {}
        results: dict[int, dict] = {}
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as ex:
            for i, f in enumerate(files, 1):
                out_html = outdir / (f.stem + ".html")
                print(f"[submit {i}/{len(files)}] {f.name} -> {out_html.name}")
                futures[ex.submit(build_map_and_metrics, f, cfg, out_html)] = (i, f, out_html)
            total = len(futures)
            done = 0
            for fut in concurrent.futures.as_completed(futures):
                i, f, out_html = futures[fut]
                done += 1
                try:
                    metrics = fut.result()
                    print(f"[{done}/{total}] Done {f.name} -> {out_html.name}")
                    results[i] = metrics
                except Exception as e:  # noqa: BLE001
                    print(f"ERROR processing {f}: {e}", file=sys.stderr)
                    results[i] = {
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
                    }
        for i in range(1, len(files) + 1):
            rows.append(results[i])

    # Write CSV
    fieldnames = [
        "file", "html", "n_points", "n_bbox", "n_filtered", "largest_comp_size",
        "connection_radius_m", "length_m", "angle_bias_m_per_rad", "L0_m", "penalty_factor", "error"
    ]
    for r in rows:
        r.setdefault("error", "")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote CSV: {csv_path}")
    print(f"Wrote {len([r for r in rows if not r['error']])} HTML maps to: {outdir}")
    return csv_path

def parse_args():
    p = argparse.ArgumentParser(description="Batch-build cluster maps and export distances CSV.")
    p.add_argument("indir", type=str, help="Directory containing input files (JSON-within-.txt is fine)." )
    p.add_argument("--outdir", type=str, default=None, help="Directory to write HTML maps (default: <indir>/maps).")
    p.add_argument("--csv", type=str, default=None, help="Path to write CSV summary (default: <outdir>/distances.csv)." )
    p.add_argument("--pattern", action="append", default=["*.txt", "*.json"], help="Glob pattern(s) to include (can repeat). Default: *.txt, *.json" )
    # Config overrides
    p.add_argument("--city", type=str, default=None, help="City preset name (overrides bbox if supplied).")
    p.add_argument("--lat-min", type=float, default=53.3)
    p.add_argument("--lat-max", type=float, default=53.8)
    p.add_argument("--lon-min", type=float, default=9.6)
    p.add_argument("--lon-max", type=float, default=10.35)
    p.add_argument("--k", type=int, default=6)
    p.add_argument("--n-sigmas", type=float, default=3.0)
    p.add_argument("--L0", type=float, default=50.0)
    p.add_argument("--penalty-factor", type=float, default=3.0)
    p.add_argument("--angle-bias", type=float, default=8.0, help="meters per radian")
    p.add_argument("--step-penalty", type=float, default=5.0, help="meters per edge")
    p.add_argument("--min-edge-cost", type=float, default=15.0, help="meters floor per edge")
    p.add_argument("--bounds-expand", type=float, default=2.0)
    p.add_argument("--workers", type=int, default=1, help="Number of parallel workers (default: 1). Use 0 or 1 for serial execution.")
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
    city=a.city,
        lat_min=a.lat_min, lat_max=a.lat_max, lon_min=a.lon_min, lon_max=a.lon_max,
        k=a.k, n_sigmas=a.n_sigmas,
        L0=a.L0, penalty_factor=a.penalty_factor,
        angle_bias_m_per_rad=a.angle_bias, step_penalty_m=a.step_penalty, min_edge_cost_m=a.min_edge_cost,
        bounds_expand=a.bounds_expand,
    )

    try:
        run_batch(indir, outdir, a.pattern, cfg, workers=a.workers, csv_path=csv_path)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
