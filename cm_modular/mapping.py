from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
import folium
import numpy as np
import pandas as pd

@dataclass
class MapStyle:
    palette: Sequence[str] = (
        "#2ecc71",  # largest cluster
        "#1f77b4", "#ff7f0e", "#9467bd", "#8c564b",
        "#e377c2", "#17becf", "#bcbd22", "#d62728", "#7f7f7f",
    )
    path_color: str = "#111111"

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
        cluster_sizes: list[int],
        order: list[int],
        path_indices: list[int] | None,
        start_idx: int | None,
        end_idx: int | None,
        length_m: float,
        angle_bias_m_per_rad: float,
        bounds_expand: float = 2.0,
    ) -> folium.Map:
        # compute overall bbox (fallback)
        lat_min, lat_max = filtered["lat"].min(), filtered["lat"].max()
        lon_min, lon_max = filtered["lon"].min(), filtered["lon"].max()
        lat_c = (lat_min + lat_max) / 2.0
        lon_c = (lon_min + lon_max) / 2.0

        # start map centered on overall center (may be re-fit below)
        m = folium.Map(location=[lat_c, lon_c], tiles="OpenStreetMap")

        for _, r in filtered.iterrows():
            folium.CircleMarker(
                location=[r.lat, r.lon],
                radius=4,
                color=self.color_for_cluster(int(r.cluster)),
                fill=True,
                fill_opacity=0.9,
                weight=1,
                tooltip=f"cluster {int(r.cluster)}",
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

        if path_indices:
            latlons = list(zip(filtered.loc[path_indices, "lat"], filtered.loc[path_indices, "lon"]))
            folium.PolyLine(
                locations=latlons,
                weight=3,
                color=self.style.path_color,
                opacity=0.9,
                tooltip=f"Angle-biased diameter ~{length_m:.2f} km (bias={angle_bias_m_per_rad} m/rad)",
            ).add_to(m)
            if start_idx is not None and end_idx is not None:
                s_lat = filtered.loc[start_idx, "lat"]; s_lon = filtered.loc[start_idx, "lon"]
                e_lat = filtered.loc[end_idx, "lat"];   e_lon = filtered.loc[end_idx, "lon"]
                folium.Marker([s_lat, s_lon], tooltip="Start", icon=folium.Icon(color="green", icon="play")).add_to(m)
                folium.Marker([e_lat, e_lon], tooltip="End", icon=folium.Icon(color="red", icon="stop")).add_to(m)

        largest_size = cluster_sizes[order[0]] if order else 0
        legend_html = f"""
        <div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999;
                    background: white; padding: 10px 12px; border: 1px solid #ccc;
                    border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.2); font-size:12px;">
          <div style="font-weight:600; margin-bottom:6px;">Clusters & Angle-biased Path</div>
          <div><span style="display:inline-block;width:10px;height:10px;background:{self.style.palette[0]};border:1px solid #333;margin-right:6px;"></span>largest cluster ({largest_size} pts)</div>
          <div><span style="display:inline-block;width:10px;height:1px;background:#111;margin:0 6px 0 0;display:inline-block;vertical-align:middle;"></span>length path ≈ {length_m:.0f} m</div>
          <div>turn bias: {angle_bias_m_per_rad} m per rad</div>
          <div><span style="display:inline-block;width:10px;height:10px;background:#7f8c8d;border:1px solid #333;margin-right:6px;"></span>outliers</div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        # If a route exists, fit bounds tightly around the route and expand by 1.5x.
        if path_indices and len(path_indices) >= 2:
            pts = filtered.loc[path_indices, ["lat", "lon"]].to_numpy()
            lat_min_r, lon_min_r = float(pts[:, 0].min()), float(pts[:, 1].min())
            lat_max_r, lon_max_r = float(pts[:, 0].max()), float(pts[:, 1].max())
            lat_c_r = (lat_min_r + lat_max_r) / 2.0
            lon_c_r = (lon_min_r + lon_max_r) / 2.0
            half_lat = (lat_max_r - lat_min_r) / 2.0
            half_lon = (lon_max_r - lon_min_r) / 2.0
            factor = 1.5
            lat_min2 = lat_c_r - factor * half_lat
            lat_max2 = lat_c_r + factor * half_lat
            lon_min2 = lon_c_r - factor * half_lon
            lon_max2 = lon_c_r + factor * half_lon
            # avoid degenerate bounds
            if lat_max2 - lat_min2 < 1e-6:
                lat_min2 -= 1e-4; lat_max2 += 1e-4
            if lon_max2 - lon_min2 < 1e-6:
                lon_min2 -= 1e-4; lon_max2 += 1e-4
            m.fit_bounds([[lat_min2, lon_min2], [lat_max2, lon_max2]])
        else:
            # fallback: keep previous behavior (expand overall bbox by bounds_expand)
            lat_c = (lat_min + lat_max) / 2.0
            lon_c = (lon_min + lon_max) / 2.0
            half_lat = (lat_max - lat_min) / 2.0
            half_lon = (lon_max - lon_min) / 2.0
            lat_min2 = lat_c - bounds_expand * half_lat
            lat_max2 = lat_c + bounds_expand * half_lat
            lon_min2 = lon_c - bounds_expand * half_lon
            lon_max2 = lon_c + bounds_expand * half_lon
            m.fit_bounds([[lat_min2, lon_min2], [lat_max2, lon_max2]])

        return m
