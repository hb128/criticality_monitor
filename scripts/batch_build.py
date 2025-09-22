#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
import os
import json
import concurrent.futures
from pathlib import Path
from typing import Iterable, Set
from datetime import datetime

from cm_modular.pipeline import PipelineConfig, Pipeline

def iter_files(indir: Path, patterns: list[str]) -> Iterable[Path]:
    """Yield files in *indir* matching any of the glob *patterns* (non-recursive)."""
    seen = set()
    for pat in patterns:
        for p in indir.glob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield p

def load_batch_state(state_file: Path) -> tuple[Set[str], list[dict]]:
    """Load batch processing state including processed files and results."""
    if not state_file.exists():
        return set(), []
    
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            processed_files = set(data.get('processed_files', []))
            results = data.get('results', [])
            return processed_files, results
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load state file {state_file}: {e}")
        return set(), []

def save_batch_state(state_file: Path, processed_files: Set[str], results: list[dict], last_run: str = None):
    """Save batch processing state including processed files and results."""
    data = {
        'metadata': {
            'last_run': last_run or datetime.now().isoformat(),
            'total_files': len(processed_files),
            'total_results': len(results),
            'version': '1.0'
        },
        'processed_files': sorted(list(processed_files)),
        'results': results
    }
    
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save state file {state_file}: {e}")

def get_file_signature(file_path: Path) -> str:
    """Get a signature for a file (path + modification time + size)."""
    try:
        stat = file_path.stat()
        return f"{file_path}|{stat.st_mtime}|{stat.st_size}"
    except OSError:
        return str(file_path)

def filter_new_files(files: list[Path], processed_files: Set[str]) -> tuple[list[Path], list[Path]]:
    """Filter files into new and already processed lists."""
    new_files = []
    skipped_files = []
    
    for file_path in files:
        signature = get_file_signature(file_path)
        if signature in processed_files:
            skipped_files.append(file_path)
        else:
            new_files.append(file_path)
    
    return new_files, skipped_files

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
    incremental: bool = True,
    state_file: Path | None = None,
) -> Path:
    """Run batch processing of files and write JSON state.

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
    incremental : bool, default True
        If True, only process files that haven't been processed before.
    state_file : Path | None
        Path to state file for tracking processed files. If None, uses outdir / "results.json".

    Returns
    -------
    Path
        Path to written JSON state file.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    
    if state_file is None:
        state_file = outdir / "results.json"
    
    # Load existing state (processed files and results)
    processed_files = set()
    existing_results = []
    
    if incremental:
        processed_files, existing_results = load_batch_state(state_file)
        print(f"Loaded {len(processed_files)} previously processed files and {len(existing_results)} results from state")

    files = sorted(iter_files(indir, patterns))
    if not files:
        raise FileNotFoundError(f"No files matched in {indir} with patterns {patterns}")
    
    # Filter to only new files if incremental mode
    if incremental:
        new_files, skipped_files = filter_new_files(files, processed_files)
        print(f"Found {len(files)} total files, {len(new_files)} new, {len(skipped_files)} already processed")
        files = new_files
        
        if not new_files:
            print("No new files to process")
            return state_file
    else:
        print(f"Processing all {len(files)} files (incremental mode disabled)")

    all_results: list[dict] = existing_results.copy()  # Start with existing data
    workers_eff = workers if workers and workers > 1 else 1
    newly_processed = set()  # Track files processed in this run
    new_results = []  # Track only new results from this run

    if workers_eff == 1:
        for i, f in enumerate(files, 1):
            try:
                out_html = outdir / (f.stem + ".html")
                print(f"[{i}/{len(files)}] Processing {f.name} -> {out_html.name}")
                metrics = build_map_and_metrics(f, cfg, out_html)
                new_results.append(metrics)
                all_results.append(metrics)
                newly_processed.add(get_file_signature(f))
            except Exception as e:  # noqa: BLE001
                print(f"ERROR processing {f}: {e}", file=sys.stderr)
                error_result = {
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
                new_results.append(error_result)
                all_results.append(error_result)
                # Still mark as processed even if there was an error
                newly_processed.add(get_file_signature(f))
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
                    newly_processed.add(get_file_signature(f))
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
                    # Still mark as processed even if there was an error
                    newly_processed.add(get_file_signature(f))
        
        # Add parallel results to our collections
        for i in range(1, len(files) + 1):
            result = results[i]
            new_results.append(result)
            all_results.append(result)

    # Save combined state (processed files + all results)
    if incremental and newly_processed:
        processed_files.update(newly_processed)
        save_batch_state(state_file, processed_files, all_results)
        print(f"Updated state file with {len(newly_processed)} newly processed files")

    new_files_count = len(newly_processed) if incremental else len(files)
    successful_files = len([r for r in new_results if not r.get('error')])
    
    print(f"Processed {new_files_count} files, {successful_files} successful")
    print(f"Total records in state: {len(all_results)}")
    print(f"Wrote {successful_files} HTML maps to: {outdir}")
    return state_file

def parse_args():
    p = argparse.ArgumentParser(description="Batch-build cluster maps and export results to JSON state file.")
    p.add_argument("indir", type=str, help="Directory containing input files (JSON-within-.txt is fine)." )
    p.add_argument("--outdir", type=str, default=None, help="Directory to write HTML maps (default: <indir>/maps).")
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
    # Incremental processing options
    p.add_argument("--no-incremental", dest="incremental", action="store_false", help="Disable incremental processing (process all files)")
    p.add_argument("--state-file", type=str, default=None, help="Path to state file for tracking processed files (default: <outdir>/results.json)")
    p.add_argument("--reset-state", action="store_true", help="Reset state file before processing (process all files and rebuild state)")
    return p.parse_args()

def main():
    a = parse_args()
    indir = Path(a.indir).expanduser().resolve()
    if not indir.exists() or not indir.is_dir():
        print(f"Input directory not found: {indir}", file=sys.stderr)
        sys.exit(2)

    outdir = Path(a.outdir).expanduser().resolve() if a.outdir else (indir / "maps")
    outdir.mkdir(parents=True, exist_ok=True)

    state_file = Path(a.state_file).expanduser().resolve() if a.state_file else (outdir / "results.json")
    
    # Handle state reset
    if a.reset_state and state_file.exists():
        print(f"Resetting state file: {state_file}")
        state_file.unlink()

    cfg = PipelineConfig(
        city=a.city,
        lat_min=a.lat_min, lat_max=a.lat_max, lon_min=a.lon_min, lon_max=a.lon_max,
        k=a.k, n_sigmas=a.n_sigmas,
        L0=a.L0, penalty_factor=a.penalty_factor,
        angle_bias_m_per_rad=a.angle_bias, step_penalty_m=a.step_penalty, min_edge_cost_m=a.min_edge_cost,
        bounds_expand=a.bounds_expand,
    )

    try:
        state_path = run_batch(
            indir, outdir, a.pattern, cfg, 
            workers=a.workers, 
            incremental=a.incremental,
            state_file=state_file
        )
        print(f"Batch processing completed. State saved to: {state_path}")
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
