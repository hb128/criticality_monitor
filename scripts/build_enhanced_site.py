#!/usr/bin/env python3
"""
Buildef build_enhanced_site(
    data_path: Union[Path, str],
    outdir: Path,
    city: str = "Hamburg",
    copy_maps: bool = True,
    maps_subdir: str = "maps",
    recent_limit: int = 30
    ) -> None:nced Criticality Monitor website with header, metrics, leaderboard, and map.

This creates a more sophisticated layout compared to build_site.py:
- Professional header with city branding
- Recent distances plot (time series)
- Leaderboard of the city with the longest rides
- Interactive map at the bottom
- Responsive design
"""
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
    prepare_recent_data,
    prepare_city_leaderboard_data,
    prepare_current_stats,
    prepare_plot_data,
)
from cm_modular.website_templates import render_enhanced_html


def build_enhanced_site(
    data_path: Union[Path, str],
    outdir: Path,
    city: str = "Hamburg",
    copy_maps: bool = True,
    maps_subdir: str = "maps",
    recent_limit: int = 30
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
    if copy_maps and 'html' in df.columns:
        maps_dir = outdir / maps_subdir
        maps_dir.mkdir(exist_ok=True)
        
        for i, row in df.iterrows():
            html_path = row.get('html')
            if pd.notna(html_path) and Path(html_path).exists():
                src_path = Path(html_path)
                filename = make_safe_filename(f"{i:04d}_{src_path.name}")
                dest_path = maps_dir / filename
                
                if not dest_path.exists():
                    shutil.copy2(src_path, dest_path)
                
                # Store relative link for website
                rel_links.append(f"{maps_subdir}/{filename}")
    elif 'html' in df.columns:
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
    recent_data = prepare_recent_data(df, recent_limit)
    
    leaderboard_data = prepare_city_leaderboard_data(df)
    
    current_stats = prepare_current_stats(df)
    plot_data = prepare_plot_data(df, rel_links)
    
    # Render HTML
    html_content = render_enhanced_html(
        city=city,
        recent_data=recent_data,
        leaderboard_data=leaderboard_data,
        current_stats=current_stats,
        plot_data=plot_data,
    )
    
    # Write HTML file
    html_path = outdir / "index.html"
    html_path.write_text(html_content, encoding='utf-8')
    
    print(f"Enhanced site written to: {html_path}")


def parse_args():
    """Parse command line arguments."""
    p = argparse.ArgumentParser(description="Build an enhanced Criticality Monitor website.")
    p.add_argument("data", help="Path to the JSON state file (results.json)")
    p.add_argument("--outdir", default="data/sites/", help="Output directory (default: %(default)s)")
    p.add_argument("--city", default="Hamburg", help="City name (default: %(default)s)")
    p.add_argument("--copy-maps", action="store_true", help="Copy map files (default: Off)")
    p.add_argument("--maps-subdir", default="maps", help="Maps subdirectory (default: %(default)s)")
    p.add_argument("--recent-limit", type=int, default=30, help="Number of recent rides for plot (default: %(default)s)")
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
        copy_maps=args.copy_maps,
        maps_subdir=args.maps_subdir,
        recent_limit=args.recent_limit
    )


if __name__ == "__main__":
    main()
