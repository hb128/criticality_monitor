#!/usr/bin/env python3
"""
Build a static, interactive website from JSON state files.

Features
--------
- Interactive Plotly chart (line or scatter) for one or more Y columns vs X.
- Each point is clickable and opens the corresponding Folium map (from the
  `html` column) in a new tab.
- Optionally copies map HTML files into the site folder for robust relative links.
- Also renders a simple table with links for quick browsing.

Usage
-----
python scripts/build_site.py path/to/results.json \
  --outdir site \
  --x t \
  --y length_m \
  --style line \
  --title "Critical Length Over Time"

Then open site/index.html in your browser.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path
from typing import List

import pandas as pd


# --- Utilities copied/adapted from scripts/plot_metrics.py ---
import re
STAMP_RE = re.compile(r"(?P<stamp>\d{8}_\d{6})")  # e.g., 20220624_202509


def load_data(data_path: Path) -> pd.DataFrame:
    """Load data from JSON state file."""
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    if not results:
        raise ValueError(f"No results found in JSON state file: {data_path}")
    
    return pd.DataFrame(results)


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
    # Keep alnum, dash, underscore; replace others with '-'
    return "".join(c if (c.isalnum() or c in ("-", "_")) else "-" for c in base)


def build_site(
    data_path: Path,
    outdir: Path,
    *,
    x_col: str = "t",
    y_cols: List[str] | None = None,
    style: str = "line",  # "line" | "scatter"
    title: str | None = None,
    copy_maps: bool = True,
    maps_subdir: str = "maps",
    query: str | None = None,
):
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_data(data_path)
    df = ensure_time_column(df)

    if query:
        df = df.query(query)

    if y_cols is None:
        y_cols = ["length_m"]

    # Prepare links: optionally copy map HTML to site/<maps_subdir>/
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
                    # Unique, stable-ish name
                    stem = src.stem
                    safe = make_safe_filename(stem)
                    dest_name = f"{i:05d}-{safe}.html"
                    dest = maps_dir / dest_name
                    if not dest.exists():
                        shutil.copy2(src, dest)
                    rel_links.append(str(dest.relative_to(outdir)).replace("\\", "/"))
                except Exception:
                    # Fallback to original path normalized for web
                    link = str(src.relative_to(outdir)).replace("\\", "/") if src.exists() else str(src).replace("\\", "/")
                    rel_links.append(link)
            else:
                  link = str(src.relative_to(outdir)).replace("\\", "/") if src.exists() else str(src).replace("\\", "/")
                  rel_links.append(link)
        else:
            rel_links.append("")

    # Build x vector
    if x_col == "index":
        x_vals = list(range(len(df)))
        x_type = "index"
    else:
        if x_col not in df.columns and x_col == "t":
            df = ensure_time_column(df)
        if x_col not in df.columns:
            raise SystemExit(f"X column '{x_col}' not found. Available: {list(df.columns)}")
        x_series = df[x_col]
        if str(x_series.dtype).startswith("datetime64"):
            # Convert to ISO strings for Plotly
            x_vals = [None if pd.isna(v) else pd.to_datetime(v).isoformat() for v in x_series]
            x_type = "datetime"
        else:
            x_vals = x_series.tolist()
            x_type = "other"

    # Prepare data to embed
    rows_for_table = []
    for i, row in df.iterrows():
        rows_for_table.append({
            "i": int(i),
            "file": str(row.get("file", "")),
            "html": rel_links[i] if i < len(rel_links) else "",
            "t": (None if pd.isna(row.get("t")) else pd.to_datetime(row.get("t")).isoformat()) if "t" in df.columns else None,
            "length_m": float(row.get("length_m", float("nan"))) if "length_m" in df.columns else None,
            "n_filtered": int(row.get("n_filtered", 0)) if "n_filtered" in df.columns and pd.notna(row.get("n_filtered")) else None,
            "largest_comp_size": int(row.get("largest_comp_size", 0)) if "largest_comp_size" in df.columns and pd.notna(row.get("largest_comp_size")) else None,
        })

    data = {
        "x": x_vals,
        "xType": x_type,
        "yCols": [c for c in y_cols if c in df.columns],
        "series": {c: df[c].tolist() for c in y_cols if c in df.columns},
        "links": rel_links,
        "title": title or data_path.name,
        "rows": rows_for_table,
        "xLabel": x_col,
        "style": style,
    }

    # Emit a single self-contained HTML file
    index_html = outdir / "index.html"
    with index_html.open("w", encoding="utf-8") as f:
        f.write(_render_html(data))

    print(f"Wrote site to: {index_html}")


def _render_html(data: dict) -> str:
  # Use Plotly from CDN and vanilla JS. Embed JSON safely via a script[type=application/json].
  data_json = json.dumps(data).replace("</", "<\\/")  # prevent </script> breakouts
  return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html.escape(str(data.get('title', 'Metrics Plot')))}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.1.min.js"></script>
    <style>
      body {{ font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 0; }}
      header {{ padding: 12px 16px; border-bottom: 1px solid #eee; }}
      main {{ display: grid; grid-template-columns: 1.5fr 1fr; gap: 8px; padding: 8px; }}
      #chart {{ width: 100%; height: 70vh; }}
      table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
      th, td {{ border-bottom: 1px solid #eee; padding: 6px 8px; text-align: left; }}
      tr:hover {{ background: #fafafa; }}
      .muted {{ color: #888; }}
      @media (max-width: 1000px) {{ main {{ grid-template-columns: 1fr; }} }}
    </style>
  </head>
  <body>
    <header>
      <h2 style="margin: 0">{html.escape(str(data.get('title', 'Metrics Plot')))}</h2>
      <div class="muted">Hover a point or row to preview. Click a point to open its map in a new tab.</div>
    </header>
    <main>
      <div id="chart"></div>
      <div>
        <h3 style="margin: 6px 0 8px">Preview</h3>
        <div id="viewerWrap" style="border:1px solid #eee; border-radius:6px; overflow:hidden; background:#fafafa; height:48vh; margin-bottom:10px;">
          <iframe id="viewer" title="Map preview" style="width:100%; height:100%; border:0;" sandbox="allow-scripts allow-same-origin allow-popups"></iframe>
        </div>
        <h3 style="margin: 6px 0 8px">Runs</h3>
        <div class="muted" style="margin-bottom:6px">Hover a row or a point to preview; click a point to open in a new tab. Most recent first</div>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>time</th>
              <th>length_m</th>
              <th>file</th>
              <th>map</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </main>
    <script id="payload" type="application/json">{data_json}</script>
    <script>
      let DATA = null;
      try {{
        const el = document.getElementById('payload');
        DATA = JSON.parse(el.textContent);
      }} catch (e) {{
        console.error('Failed to parse embedded data', e);
        DATA = {{ x: [], yCols: [], series: {{}}, links: [], rows: [], title: 'Metrics Plot', xLabel: '' }};
      }}

      // Prepare traces
      const traces = [];
      const mode = DATA.style === 'scatter' ? 'markers' : 'lines+markers';
      const hoverBase = `<b>%{{fullData.name}}</b><br>{html.escape(str(data.get('xLabel', 'x')))}: %{{x}}<br>y: %{{y}}`;
      for (const col of DATA.yCols) {{
        traces.push({{
          x: DATA.x,
          y: DATA.series[col],
          name: col,
          mode,
          type: 'scattergl',
          hovertemplate: hoverBase + '<extra></extra>'
        }});
      }}

      const layout = {{
        xaxis: {{ title: DATA.xLabel }},
        yaxis: {{ title: DATA.yCols.join(', ') }},
        margin: {{ l: 50, r: 20, t: 20, b: 50 }},
        legend: {{ orientation: 'h' }},
      }};

      Plotly.newPlot('chart', traces, layout, {{responsive: true}});

      const links = DATA.links;
      const viewer = document.getElementById('viewer');
      const setViewer = (url) => {{
        if (!url) return;
        try {{
          if (viewer.getAttribute('src') !== url) viewer.setAttribute('src', url);
        }} catch (e) {{ console.warn('Unable to set preview iframe src', e); }}
      }};
      const openPoint = (pointIndex) => {{
        if (!links || pointIndex == null) return;
        const url = links[pointIndex];
        if (url) window.open(url, '_blank');
      }};
      const chartEl = document.getElementById('chart');
  chartEl.on('plotly_click', ev => {{
        if (!ev || !ev.points || !ev.points.length) return;
        const idx = ev.points[0].pointIndex;
        openPoint(idx);
      }});
      chartEl.on('plotly_hover', ev => {{
        if (!ev || !ev.points || !ev.points.length) return;
        const idx = ev.points[0].pointIndex;
        const url = (links && links[idx]) || '';
        if (url) setViewer(url);
      }});

      // Build table (reverse chronological if x is datetime)
      const tbody = document.getElementById('rows');
      const rows = DATA.rows.slice();
      try {{
        rows.sort((a,b) => (b.t||'').localeCompare(a.t||''));
      }} catch {{}}
      for (const r of rows) {{
        const tr = document.createElement('tr');
        tr.dataset.idx = String(r.i);
        const t = r.t ? new Date(r.t).toLocaleString() : '-';
        tr.innerHTML = `
          <td class="muted">${{r.i}}</td>
          <td>${{t}}</td>
          <td>${{r.length_m ?? ''}}</td>
          <td title="${{r.file}}">${{r.file.split(/[\\/]/).pop() || ''}}</td>
          <td>${{r.html ? `<a href="${{r.html}}" target="_blank">open</a>` : ''}}</td>
        `;
        tbody.appendChild(tr);
      }}
      // Hover preview for table rows
      tbody.addEventListener('mouseover', (e) => {{
        const tr = e.target && (e.target.closest ? e.target.closest('tr') : null);
        if (!tr || !tr.dataset) return;
        const idx = Number(tr.dataset.idx);
        if (!Number.isFinite(idx)) return;
        const url = links && links[idx];
        if (url) setViewer(url);
      }});

      // Initialize preview to the most recent row with a map
      for (const r of rows) {{
        if (r.html) {{ setViewer(r.html); break; }}
      }}
    </script>
  </body>
</html>
"""


def parse_args():
    p = argparse.ArgumentParser(description="Build an interactive website from JSON state files.")
    p.add_argument("data", help="Path to the JSON state file (e.g., results.json)")
    p.add_argument("--outdir", default="sites", help="Output directory for the static website (default: site)")
    p.add_argument("--x", default="t", help="X column (default: t; use 'index' for row index)")
    p.add_argument("--y", nargs="+", default=["length_m"], help="Y columns to plot (default: length_m)")
    p.add_argument("--style", choices=["line", "scatter"], default="line", help="Plot style (default: line)")
    p.add_argument("--title", default=None, help="Optional page title")
    p.add_argument("--copy-maps", default=False, action="store_false", help="Do not copy map HTML files into the site folder")
    p.add_argument("--maps-subdir", default="maps", help="Subdirectory under outdir for copied maps (default: maps)")
    p.add_argument("--query", default=None, help="Optional pandas query to filter rows")
    return p.parse_args()


def main():
    args = parse_args()
    data_path = Path(args.data).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    build_site(
        data_path=data_path,
        outdir=outdir,
        x_col=args.x,
        y_cols=args.y,
        style=args.style,
        title=args.title,
        copy_maps=args.copy_maps,
        maps_subdir=args.maps_subdir,
        query=args.query,
    )


if __name__ == "__main__":
    main()
