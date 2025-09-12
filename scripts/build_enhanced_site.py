#!/usr/bin/env python3
"""
Build an enhanced Critical Mass website with header, metrics, leaderboard, and map.

This creates a more sophisticated layout compared to build_site.py:
- Professional header with city branding
- Recent distances plot (time series)
- Leaderboard of longest rides
- Interactive map at the bottom
- Responsive design
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path
from typing import List
from datetime import datetime

import pandas as pd
import numpy as np


# --- Utilities from build_site.py ---
import re
STAMP_RE = re.compile(r"(?P<stamp>\d{8}_\d{6})")


def parse_timestamp_from_path(s: str):
    if not isinstance(s, str):
        return pd.NaT
    m = STAMP_RE.search(s)
    if not m:
        return pd.NaT
    return pd.to_datetime(m.group("stamp"), format="%Y%m%d_%H%M%S")


def ensure_time_column(df: pd.DataFrame) -> pd.DataFrame:
    t = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    for col in ("file", "html"):
        if col in df.columns:
            parsed = df[col].map(parse_timestamp_from_path)
            t = parsed.where(parsed.notna(), t)
    if t.notna().any():
        df = df.copy()
        df["t"] = t
    return df


def make_safe_filename(base: str) -> str:
    return "".join(c if (c.isalnum() or c in ("-", "_")) else "-" for c in base)


def build_enhanced_site(
    csv_path: Path,
    outdir: Path,
    *,
    city: str = "Hamburg",
    copy_maps: bool = True,
    maps_subdir: str = "maps",
    query: str | None = None,
    recent_limit: int = 30,
    leaderboard_limit: int = 10,
):
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    df = ensure_time_column(df)

    if query:
        df = df.query(query)

    # Prepare map links
    rel_links: list[str] = []
    maps_dir = outdir / maps_subdir
    if copy_maps:
        maps_dir.mkdir(parents=True, exist_ok=True)
    
    for i, row in df.iterrows():
        link = row.get("html", None)
        if isinstance(link, str) and link:
            src = Path(link)
            if copy_maps and src.exists():
                try:
                    stem = src.stem
                    safe = make_safe_filename(stem)
                    dest_name = f"{i:05d}-{safe}.html"
                    dest = maps_dir / dest_name
                    if not dest.exists():
                        shutil.copy2(src, dest)
                    rel_links.append(str(dest.relative_to(outdir)).replace("\\", "/"))
                except Exception:
                    link = str(src.relative_to(outdir)).replace("\\", "/") if src.exists() else str(src).replace("\\", "/")
                    rel_links.append(link)
            else:
                link = str(src.relative_to(outdir)).replace("\\", "/") if src.exists() else str(src).replace("\\", "/")
                rel_links.append(link)
        else:
            rel_links.append("")

    # Prepare data for different sections
    recent_data = prepare_recent_data(df, recent_limit)
    leaderboard_data = prepare_leaderboard_data(df, leaderboard_limit)
    current_stats = prepare_current_stats(df)
    
    # Prepare plot data
    plot_data = prepare_plot_data(df, rel_links)

    # Build the website
    index_html = outdir / "index.html"
    with index_html.open("w", encoding="utf-8") as f:
        f.write(render_enhanced_html(
            city=city,
            recent_data=recent_data,
            leaderboard_data=leaderboard_data,
            current_stats=current_stats,
            plot_data=plot_data,
        ))

    print(f"Enhanced site written to: {index_html}")


def prepare_recent_data(df: pd.DataFrame, limit: int) -> dict:
    """Prepare data for the recent rides section."""
    recent_df = df.sort_values('t', ascending=False).head(limit) if 't' in df.columns else df.head(limit)
    
    # For plotting
    x_vals = []
    y_vals = []
    if 't' in df.columns:
        plot_df = df.sort_values('t').tail(limit)
        for _, row in plot_df.iterrows():
            if pd.notna(row.get('t')) and pd.notna(row.get('length_m')):
                try:
                    x_vals.append(pd.to_datetime(row['t']).isoformat())
                    y_vals.append(float(row['length_m']))
                except:
                    pass  # Skip invalid entries
    
    return {
        'x': x_vals,
        'y': y_vals,
        'records': [],  # Simplified for now to avoid JSON serialization issues
    }


def prepare_leaderboard_data(df: pd.DataFrame, limit: int) -> dict:
    """Prepare leaderboard of longest rides."""
    if 'length_m' not in df.columns:
        return {'records': []}
    
    leaderboard = df.nlargest(limit, 'length_m')
    records = []
    
    for rank, (_, row) in enumerate(leaderboard.iterrows(), 1):
        # Handle date conversion safely
        date_str = 'Unknown'
        if 't' in row and pd.notna(row['t']):
            try:
                date_str = pd.to_datetime(row['t']).strftime('%d.%m.%Y')
            except:
                date_str = 'Unknown'
        
        record = {
            'rank': rank,
            'length_m': float(row['length_m']) if pd.notna(row['length_m']) else 0,
            'date': date_str,
            'participants': int(row.get('n_filtered', 0)) if 'n_filtered' in row and pd.notna(row.get('n_filtered')) else None,
        }
        records.append(record)
    
    return {'records': records}


def prepare_current_stats(df: pd.DataFrame) -> dict:
    """Prepare current statistics."""
    if df.empty:
        return {
            'total_rides': 0,
            'latest_length': 0,
            'latest_date': 'No data',
            'avg_length': 0,
            'total_distance': 0,
        }
    
    latest = df.loc[df.index[-1]] if not df.empty else {}
    
    # Handle timestamp conversion safely
    latest_date_str = 'Unknown'
    if 't' in latest and pd.notna(latest['t']):
        try:
            latest_date_str = pd.to_datetime(latest['t']).strftime('%d.%m.%Y - %H:%M')
        except:
            latest_date_str = 'Unknown'
    
    return {
        'total_rides': len(df),
        'latest_length': float(latest.get('length_m', 0)) if pd.notna(latest.get('length_m')) else 0,
        'latest_date': latest_date_str,
        'avg_length': float(df['length_m'].mean()) if 'length_m' in df.columns else 0,
        'total_distance': float(df['length_m'].sum()) if 'length_m' in df.columns else 0,
    }


def prepare_plot_data(df: pd.DataFrame, rel_links: list[str]) -> dict:
    """Prepare data for the interactive plot."""
    if 't' not in df.columns or 'length_m' not in df.columns:
        return {'x': [], 'y': [], 'links': []}
    
    plot_df = df.sort_values('t').dropna(subset=['t', 'length_m'])
    
    return {
        'x': [pd.to_datetime(row['t']).isoformat() for _, row in plot_df.iterrows()],
        'y': [float(row['length_m']) for _, row in plot_df.iterrows()],
        'links': [rel_links[i] for i in plot_df.index if i < len(rel_links)],
    }


def render_enhanced_html(
    city: str,
    recent_data: dict,
    leaderboard_data: dict,
    current_stats: dict,
    plot_data: dict,
) -> str:
    """Render the enhanced HTML page."""
    
    data_json = json.dumps({
        'recent': recent_data,
        'leaderboard': leaderboard_data,
        'stats': current_stats,
        'plot': plot_data,
    }).replace("</", "<\\/")
    
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Critical Mass {html.escape(city)}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.1.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; 
            line-height: 1.6; 
            color: #2c3e50;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 0 20px;
        }}
        
        /* Header */
        .hero {{ 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 20px 0;
            text-align: center;
            border-radius: 0 0 20px 20px;
            margin-bottom: 20px;
        }}
        
        .hero h1 {{ 
            font-size: 2rem; 
            font-weight: 700; 
            color: #2c3e50;
            margin-bottom: 0;
        }}
        
        .hero .subtitle {{ 
            font-size: 1.2rem; 
            color: #7f8c8d;
            margin-bottom: 20px;
        }}
        
        .hero .current-stats {{ 
            display: flex; 
            justify-content: center; 
            gap: 40px; 
            flex-wrap: wrap;
        }}
        
        .stat-item {{ 
            text-align: center;
        }}
        
        .stat-value {{ 
            font-size: 2rem; 
            font-weight: 700; 
            color: #e74c3c;
        }}
        
        .stat-label {{ 
            font-size: 0.9rem; 
            color: #7f8c8d; 
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* Main content */
        .main-content {{ 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        
        /* 2x2 Grid Layout for iPad Landscape */
        .content-grid {{ 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            grid-template-rows: 35vh 35vh;
            gap: 15px; 
            min-height: 70vh; /* Reduced for iPad 3 */
        }}
        
        .grid-item {{
            background: rgba(248, 249, 250, 0.8);
            border-radius: 15px;
            padding: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden; /* Prevent content from spilling out */
            display: flex;
            flex-direction: column;
        }}
        
        /* Chart section - Top Left */
        .chart-section {{ 
            
        }}
        
        .chart-section h2 {{ 
            margin-bottom: 10px; 
            color: #2c3e50;
            font-size: 1.1rem;
        }}
        
        #chart {{ 
            width: 100%; 
            height: 100%;
            min-height: 200px;
            border-radius: 10px;
            flex: 1; /* Take remaining space */
        }}
        
        /* Leaderboard - Top Right */
        .leaderboard {{
            
        }}
        
        .leaderboard h2 {{ 
            margin-bottom: 10px; 
            color: #2c3e50;
            font-size: 1.1rem;
            flex-shrink: 0; /* Don't shrink the header */
        }}
        
        #leaderboard-list {{
            flex: 1; /* Take remaining space */
            overflow-y: auto;
            max-height: 100%;
        }}
        
        .leaderboard-item {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            padding: 6px; 
            margin-bottom: 6px; 
            background: white; 
            border-radius: 6px;
            transition: transform 0.2s;
            font-size: 0.8rem;
        }}
        
        .leaderboard-item:hover {{ 
            transform: translateY(-1px); 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .rank {{ 
            font-weight: 700; 
            font-size: 0.85rem; 
            color: #e74c3c;
            min-width: 20px;
        }}
        
        .distance {{ 
            font-weight: 600; 
            color: #2c3e50;
            font-size: 0.8rem;
        }}
        
        .date {{ 
            font-size: 0.8rem; 
            color: #7f8c8d;
        }}
        
        /* Map section - Bottom Left */
        .map-section {{ 
            
        }}
        
        .map-section h2 {{ 
            margin-bottom: 10px; 
            color: #2c3e50;
            font-size: 1.1rem;
            flex-shrink: 0; /* Don't shrink the header */
        }}
        
        .map-container {{ 
            width: 100%; 
            flex: 1; /* Take all remaining space */
            border-radius: 10px; 
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            min-height: 180px;
        }}
        
        #latest-map {{ 
            width: 100%; 
            height: 100%; 
            border: none;
        }}
        
        /* Stats section - Bottom Right */
        .stats-section {{
            
        }}
        
        .stats-section h2 {{ 
            margin-bottom: 10px; 
            color: #2c3e50;
            font-size: 1.1rem;
            flex-shrink: 0; /* Don't shrink the header */
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr 1fr;
            gap: 8px;
            flex: 1; /* Take remaining space */
            min-height: 150px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 60px;
        }}
        
        .stat-card-value {{
            font-size: 1.3rem;
            font-weight: 700;
            color: #e74c3c;
            margin-bottom: 3px;
            line-height: 1;
        }}
        
        .stat-card-label {{
            font-size: 0.7rem;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            line-height: 1;
        }}
        
        /* Responsive */
        @media (max-width: 1023px) {{
            .content-grid {{ 
                grid-template-columns: 1fr; 
                grid-template-rows: auto auto auto auto;
                min-height: auto;
            }}
            
            .grid-item {{
                height: 40vh;
                min-height: 300px;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr 1fr;
                min-height: 120px;
            }}
        }}
        
        @media (max-width: 768px) {{
            .hero h1 {{ 
                font-size: 2rem;
            }}
            
            .hero .current-stats {{ 
                gap: 20px;
            }}
            
            .container {{ 
                padding: 0 15px;
            }}
            
            .grid-item {{
                height: 40vh;
                min-height: 300px;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .stat-card-value {{
                font-size: 1.5rem;
            }}
        }}
        
        /* Animation */
        .main-content {{ 
            animation: fadeInUp 0.6s ease-out;
        }}
        
        @keyframes fadeInUp {{
            from {{ 
                opacity: 0; 
                transform: translateY(30px);
            }}
            to {{ 
                opacity: 1; 
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Hero Section -->
        <section class="hero">
            <h1>Critical Mass {html.escape(city)}</h1>
        </section>

        <!-- Main Content - 2x2 Grid -->
        <section class="main-content">
            <div class="content-grid">
                <!-- Top Left: Chart Section -->
                <div class="chart-section grid-item">
                    <h2>📈 Distance Over Time</h2>
                    <div id="chart"></div>
                </div>

                <!-- Top Right: Leaderboard -->
                <div class="leaderboard grid-item">
                    <h2>🏆 Longest Routes</h2>
                    <div id="leaderboard-list"></div>
                </div>
                
                <!-- Bottom Left: Map Section -->
                <div class="map-section grid-item">
                    <h2>🗺️ Latest Route</h2>
                    <div class="map-container">
                        <iframe id="latest-map" src="" title="Latest Critical Mass Route"></iframe>
                    </div>
                </div>
                
                <!-- Bottom Right: Stats Section -->
                <div class="stats-section grid-item">
                    <h2>� Statistics</h2>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-card-value" id="total-distance">{current_stats['total_distance']:.0f}m</div>
                            <div class="stat-card-label">Total Distance</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-value" id="max-distance">0m</div>
                            <div class="stat-card-label">Max Length</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-value">{current_stats['total_rides']}</div>
                            <div class="stat-card-label">Total Rides</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-value">{current_stats['avg_length']:.0f}m</div>
                            <div class="stat-card-label">Avg Length</div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </div>

    <script id="payload" type="application/json">{data_json}</script>
    <script>
        let DATA = null;
        try {{
            const el = document.getElementById('payload');
            DATA = JSON.parse(el.textContent);
        }} catch (e) {{
            console.error('Failed to parse embedded data', e);
            DATA = {{ plot: {{ x: [], y: [], links: [] }}, leaderboard: {{ records: [] }} }};
        }}

        // Initialize chart
        if (DATA.plot && DATA.plot.x.length > 0) {{
            const trace = {{
                x: DATA.plot.x,
                y: DATA.plot.y,
                type: 'scattergl',
                mode: 'lines+markers',
                name: 'Route Length',
                line: {{ color: '#e74c3c', width: 3 }},
                marker: {{ color: '#e74c3c', size: 6 }},
                hovertemplate: '<b>%{{y:.0f}}m</b><br>%{{x}}<extra></extra>'
            }};

            const layout = {{
                xaxis: {{ title: 'Date' }},
                yaxis: {{ title: 'Distance (meters)' }},
                margin: {{ l: 60, r: 20, t: 20, b: 60 }},
                plot_bgcolor: 'rgba(0,0,0,0)',
                paper_bgcolor: 'rgba(0,0,0,0)',
                font: {{ family: 'Segoe UI, system-ui, sans-serif' }}
            }};

            Plotly.newPlot('chart', [trace], layout, {{ responsive: true }});

            // Handle chart clicks
            document.getElementById('chart').on('plotly_click', function(data) {{
                const pointIndex = data.points[0].pointIndex;
                const mapUrl = DATA.plot.links[pointIndex];
                if (mapUrl) {{
                    window.open(mapUrl, '_blank');
                }}
            }});
        }}

        // Build leaderboard
        const leaderboardContainer = document.getElementById('leaderboard-list');
        let maxDistance = 0;
        if (DATA.leaderboard && DATA.leaderboard.records) {{
            DATA.leaderboard.records.forEach(record => {{
                const item = document.createElement('div');
                item.className = 'leaderboard-item';
                item.innerHTML = `
                    <div class="rank">#${{record.rank}}</div>
                    <div>
                        <div class="distance">${{record.length_m.toFixed(0)}}m</div>
                        <div class="date">${{record.date}}</div>
                    </div>
                `;
                leaderboardContainer.appendChild(item);
                
                // Track max distance
                if (record.length_m > maxDistance) {{
                    maxDistance = record.length_m;
                }}
            }});
        }}
        
        // Update max distance display
        const maxDistanceElement = document.getElementById('max-distance');
        if (maxDistanceElement) {{
            maxDistanceElement.textContent = maxDistance.toFixed(0) + 'm';
        }}

        // Load latest map
        const mapFrame = document.getElementById('latest-map');
        if (DATA.plot && DATA.plot.links && DATA.plot.links.length > 0) {{
            const latestMapUrl = DATA.plot.links[DATA.plot.links.length - 1];
            if (latestMapUrl) {{
                mapFrame.src = latestMapUrl;
            }}
        }}
    </script>
</body>
</html>"""


def parse_args():
    p = argparse.ArgumentParser(description="Build an enhanced Critical Mass website.")
    p.add_argument("csv", help="Path to the metrics CSV (e.g., distances.csv)")
    p.add_argument("--outdir", default="site", help="Output directory (default: site)")
    p.add_argument("--city", default="Hamburg", help="City name (default: Hamburg)")
    p.add_argument("--no-copy-maps", dest="copy_maps", action="store_false", help="Don't copy map files")
    p.add_argument("--maps-subdir", default="maps", help="Maps subdirectory (default: maps)")
    p.add_argument("--query", default=None, help="Pandas query to filter data")
    p.add_argument("--recent-limit", type=int, default=30, help="Number of recent rides for plot (default: 30)")
    p.add_argument("--leaderboard-limit", type=int, default=10, help="Number of entries in leaderboard (default: 10)")
    return p.parse_args()


def main():
    args = parse_args()
    csv_path = Path(args.csv).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    
    build_enhanced_site(
        csv_path=csv_path,
        outdir=outdir,
        city=args.city,
        copy_maps=args.copy_maps,
        maps_subdir=args.maps_subdir,
        query=args.query,
        recent_limit=args.recent_limit,
        leaderboard_limit=args.leaderboard_limit,
    )


if __name__ == "__main__":
    main()
