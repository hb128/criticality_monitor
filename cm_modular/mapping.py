from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
import json
from datetime import datetime
import folium
import numpy as np
import pandas as pd
import pytz

@dataclass
class MapStyle:
    palette: Sequence[str] = (
        "#2ecc71",  # largest cluster
        "#1f77b4", "#ff0e2e", "#9467bd", "#8c564b",
        "#e377c2", "#17becf", "#bcbd22", "#3C1258", "#7f7f7f",
    )
    path_color: str = "#111111"
    path_timespan_color: str = "#ff9800"  # orange for path-timespan points

class MapBuilder:
    """Build a Folium map with clusters, outliers, and the diameter path overlay."""
    def __init__(self, style: MapStyle | None = None):
        self.style = style or MapStyle()

    def color_for_cluster(self, cid: int) -> str:
        if cid < len(self.style.palette):
            return self.style.palette[cid]
        return self.style.palette[1 + (cid - 1) % (len(self.style.palette) - 1)]

    def build(
        self,
        filtered: pd.DataFrame,
        outliers: pd.DataFrame,
        path_indices: list[int] | None,
        bounds_expand: float = 2.0,
        path_df: pd.DataFrame | None = None,  # DataFrame of points within path-timespan
        segment_metrics: list[dict] | None = None,  # Precomputed segment metrics
    ) -> folium.Map:
        # compute overall bbox (fallback)
        lat_min, lat_max = filtered["lat"].min(), filtered["lat"].max()
        lon_min, lon_max = filtered["lon"].min(), filtered["lon"].max()
        lat_c = (lat_min + lat_max) / 2.0
        lon_c = (lon_min + lon_max) / 2.0

        # start map centered on overall center (may be re-fit below)
        m = folium.Map(location=[lat_c, lon_c], tiles="OpenStreetMap")

        # Draw all filtered points, but highlight those in path_df
        if path_df is not None and not path_df.empty:
            # Use index to match points in filtered
            path_indices_set = set(path_df.index)
            for idx, r in filtered.iterrows():
                if idx in path_indices_set and int(r.cluster) == 0:
                    folium.CircleMarker(
                        location=[r.lat, r.lon],
                        radius=5,
                        color=self.style.path_timespan_color,
                        fill=True,
                        fill_opacity=0.95,
                        weight=2,
                        tooltip=f"path-timespan (idx: {idx})",
                    ).add_to(m)
                else:
                    folium.CircleMarker(
                        location=[r.lat, r.lon],
                        radius=4,
                        color=self.color_for_cluster(int(r.cluster)),
                        fill=True,
                        fill_opacity=0.9,
                        weight=1,
                        tooltip=f"cluster {int(r.cluster)} (idx: {idx})",
                    ).add_to(m)
        else:
            for idx, r in filtered.iterrows():
                folium.CircleMarker(
                    location=[r.lat, r.lon],
                    radius=4,
                    color=self.color_for_cluster(int(r.cluster)),
                    fill=True,
                    fill_opacity=0.9,
                    weight=1,
                    tooltip=f"cluster {int(r.cluster)} (idx: {idx})",
                ).add_to(m)

        for _, r in outliers.iterrows():
            folium.CircleMarker(
                location=[r.lat, r.lon],
                radius=4,
                color="#7f8c8d",
                fill=True,
                fill_opacity=0.8,
                weight=1,
                tooltip="outlier",
            ).add_to(m)

        if segment_metrics is not None:
            # Use precomputed segment_metrics if provided
            for seg in segment_metrics:
                idx_start = seg["start"]
                idx_stop = seg["stop"]
                lat_start, lon_start = filtered.loc[idx_start]["lat"], filtered.loc[idx_start]["lon"]
                lat_stop, lon_stop = filtered.loc[idx_stop]["lat"], filtered.loc[idx_stop]["lon"]
                tooltip = f"{idx_start} → {idx_stop}, geo: {seg['geo_len']:.5f}, angle: {seg['angle_len']:.5f}"
                folium.PolyLine(
                    locations=[(lat_start, lon_start), (lat_stop, lon_stop)],
                    weight=3,
                    color=self.style.path_color,
                    opacity=0.9,
                    tooltip=tooltip,
                ).add_to(m)

        # Compute desired bounds (route-focused when available), then apply without animation
        if path_indices and len(path_indices) >= 2:
            pts = filtered.loc[path_indices, ["lat", "lon"]].to_numpy()
            lat_min_r, lon_min_r = float(pts[:, 0].min()), float(pts[:, 1].min())
            lat_max_r, lon_max_r = float(pts[:, 0].max()), float(pts[:, 1].max())
            lat_c_r = (lat_min_r + lat_max_r) / 2.0
            lon_c_r = (lon_min_r + lon_max_r) / 2.0
            half_lat = (lat_max_r - lat_min_r) / 2.0
            half_lon = (lon_max_r - lon_min_r) / 2.0
            factor = 1.2
            lat_min2 = lat_c_r - factor * half_lat
            lat_max2 = lat_c_r + factor * half_lat
            lon_min2 = lon_c_r - factor * half_lon
            lon_max2 = lon_c_r + factor * half_lon
        else:
            # fallback: expand overall bbox by bounds_expand
            lat_c = (lat_min + lat_max) / 2.0
            lon_c = (lon_min + lon_max) / 2.0
            half_lat = (lat_max - lat_min) / 2.0
            half_lon = (lon_max - lon_min) / 2.0
            lat_min2 = lat_c - bounds_expand * half_lat
            lat_max2 = lat_c + bounds_expand * half_lat
            lon_min2 = lon_c - bounds_expand * half_lon
            lon_max2 = lon_c + bounds_expand * half_lon

        # avoid degenerate bounds
        if lat_max2 - lat_min2 < 1e-6:
            lat_min2 -= 1e-4; lat_max2 += 1e-4
        if lon_max2 - lon_min2 < 1e-6:
            lon_min2 -= 1e-4; lon_max2 += 1e-4

        # Apply bounds without animation using inline JS, after map is ready and sized
        bounds = [[float(lat_min2), float(lon_min2)], [float(lat_max2), float(lon_max2)]]
        js = f"""
        <script>
        (function() {{
            var mapName = "{m.get_name()}";
            var bounds = {json.dumps(bounds)};
            var attempts = 0;
            function applyBoundsIfReady() {{
                var map = window[mapName];
                if (!map) {{
                    if (attempts++ < 40) return setTimeout(applyBoundsIfReady, 50);
                    return;
                }}
                var doFit = function() {{
                    try {{
                        map.options.zoomAnimation = false;
                        map.options.fadeAnimation = false;
                        if (map.invalidateSize) map.invalidateSize(true);
                        map.fitBounds(bounds, {{ animate: false, padding: [8,8] }});
                    }} catch (e) {{}}
                }};
                if (map.whenReady) {{ map.whenReady(function() {{ setTimeout(doFit, 0); }}); }}
                else {{ setTimeout(doFit, 0); }}
            }}
            if (document.readyState === 'complete') {{ applyBoundsIfReady(); }}
            else {{ window.addEventListener('load', applyBoundsIfReady, {{ once: true }}); }}
        }})();
        </script>
        """
        m.get_root().html.add_child(folium.Element(js))
        # Add a small live-reload script (polls HEAD for Last-Modified/ETag, falls back to body hash)
        live_reload = """
        <script>
        (function(){
            const interval = 500;
            let lastToken = null;
            async function check(){
                try{
                    const head = await fetch(window.location.href, { method: 'HEAD', cache: 'no-store' });
                    const lm = head.headers.get('Last-Modified');
                    const et = head.headers.get('ETag');
                    const token = lm || et;
                    if(token){
                        if(lastToken && token !== lastToken) return location.reload(true);
                        lastToken = token;
                        return setTimeout(check, interval);
                    }
                    const resp = await fetch(window.location.href, { cache: 'no-store' });
                    const text = await resp.text();
                    const hash = btoa(unescape(encodeURIComponent(text))).slice(0,32);
                    if(lastToken && hash !== lastToken) return location.reload(true);
                    lastToken = hash;
                }catch(e){ /* ignore */ }
                setTimeout(check, interval);
            }
            if(document.readyState === 'complete') setTimeout(check, interval);
            else window.addEventListener('load', () => setTimeout(check, interval), { once: true });
        })();
        </script>
        """
        m.get_root().html.add_child(folium.Element(live_reload))
        return m
