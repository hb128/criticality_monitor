#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import List, Union

import pandas as pd

# Import our modular components
from cm_modular.website_utils import ensure_time_column, make_safe_filename
from cm_modular.website_data import (
    prepare_city_leaderboard_data,
    prepare_current_stats,
    prepare_plot_data,
)
from cm_modular.website_templates import render_enhanced_html


def build_enhanced_site(
    data_path: Union[Path, str],
    outdir: Path,
    city: str = "Hamburg",
    html_name: str = "index.html",
    max_minutes_plot: int = 120
) -> None:
    """Build an enhanced Criticality Monitor website from JSON state file."""
    
    data_path = Path(data_path)
    print(f"Building enhanced site from {data_path}")
    print(f"Output directory: {outdir}")
    
    # Load from JSON state file
    with open(data_path, 'r', encoding='utf-8') as f:
        state_data = json.load(f)
    
    results = state_data.get('results', [])
    if not results:
        print("No results found in JSON state file")
        return
        
    df = pd.DataFrame(results)
    df = ensure_time_column(df)
    
    print(f"Processing {len(df)} records")
    
    # Create output directory
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Copy map files if requested
    rel_links: List[str] = []
    if 'html' in df.columns:
        # When not copying maps, create relative links to original files
        for i, row in df.iterrows():
            html_path = row.get('html')
            if pd.notna(html_path) and Path(html_path).exists():
                src_path = Path(html_path)
                # Create relative path from output directory to the original HTML file
                try:
                    rel_path = src_path.relative_to(outdir)
                    rel_links.append(str(rel_path).replace('\\', '/'))
                except ValueError:
                    # If relative path can't be computed, use absolute path as fallback
                    rel_links.append(f"file://{src_path.as_posix()}")
    
    # Prepare data for templates
    leaderboard_data = prepare_city_leaderboard_data(df)
    current_stats = prepare_current_stats(df)
    plot_data = prepare_plot_data(df, rel_links, max_minutes_plot=max_minutes_plot)
    
    # Render HTML
    html_content = render_enhanced_html(
        city=city,
        leaderboard_data=leaderboard_data,
        current_stats=current_stats,
        plot_data=plot_data,
    )
    
    # Write HTML file
    html_path = outdir / html_name
    html_path.write_text(html_content, encoding='utf-8')
    
    print(f"Enhanced site written to: {html_path}")


def parse_args():
    """Parse command line arguments."""
    p = argparse.ArgumentParser(description="Build an enhanced Criticality Monitor website.")
    p.add_argument("data", help="Path to the JSON state file (results.json)")
    p.add_argument("--outdir", default="data/sites/", help="Output directory (default: %(default)s)")
    p.add_argument("--city", default="Hamburg", help="City name (default: %(default)s)")
    p.add_argument("--max-minutes-plot", type=int, default=120, help="Number of minutes to show in the time series plot (default: %(default)s)")
    return p.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    data_path = Path(args.data).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    
    build_enhanced_site(
        data_path=data_path,
        outdir=outdir,
        city=args.city,
        max_minutes_plot=args.max_minutes_plot
    )


if __name__ == "__main__":
    main()
