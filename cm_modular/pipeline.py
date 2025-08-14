from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

from .io import DataLoader
from .geo import GeoUtils
from .filtering import RobustKNNFilter, DataFilter
from .graphing import GraphBuilder
from .routing import AngleBiasedRouter
from .clustering import Clusterer
from .mapping import MapBuilder

@dataclass
class PipelineConfig:
    # BBox defaults (Hamburg-ish) used in the original script
    lat_min: float = 53.3
    lat_max: float = 53.8
    lon_min: float = 9.6
    lon_max: float = 10.35

    # KNN filter
    k: int = 4
    n_sigmas: float = 3.0

    # Graph penalties
    L0: float = 50.0
    penalty_factor: float = 3.0

    # Angle-biased routing
    angle_bias_m_per_rad: float = 8.0
    step_penalty_m: float = 5.0
    min_edge_cost_m: float = 15.0

    # Map
    bounds_expand: float = 2.0

class Pipeline:
    """End-to-end pipeline that mirrors the original one-file script, modularized."""
    def __init__(self, cfg: PipelineConfig | None = None):
        self.cfg = cfg or PipelineConfig()
        self.map_builder = MapBuilder()

    def run(self, file_path: str | Path, out_html: str | Path | None = None):
        """Execute full pipeline and save a Folium map to HTML.

        Parameters
        ----------
        file_path : str | Path
            Path to JSON with `locations`.
        out_html : str | Path | None
            Output HTML file. If None, writes next to file_path with a default name.

        Returns
        -------
        (m, out_path) : (folium.Map, Path)
        """
        df = DataLoader.load_locations_json(file_path)

        # bbox filter
        hh = DataFilter.bbox(df, self.cfg.lat_min, self.cfg.lat_max, self.cfg.lon_min, self.cfg.lon_max)

        # base geometry + KNN filter
        x, y = GeoUtils.deg2meters(hh["lat"].values, hh["lon"].values)
        D = GeoUtils.pairwise_xy(x, y)
        keep, k_med = RobustKNNFilter.keep_by_knn(D, k=self.cfg.k, n_sigmas=self.cfg.n_sigmas)
        hh = hh.copy()
        hh["keep"] = keep
        filtered = hh[hh["keep"]].copy().reset_index(drop=True)
        outliers = hh[~hh["keep"]].copy().reset_index(drop=True)

        # graph on filtered
        x_f, y_f = GeoUtils.deg2meters(filtered["lat"].values, filtered["lon"].values)
        D_f = GeoUtils.pairwise_xy(x_f, y_f)
        adj, radius_m = GraphBuilder.build_graph(D_f, k_med, L0=self.cfg.L0, penalty_factor=self.cfg.penalty_factor)

        # cluster ids
        comps, sizes, order, cluster_id = Clusterer.assign_from_components(adj)
        filtered["cluster"] = cluster_id

        # diameter path on largest component using angle-biased metric
        path_indices: list[int] = []
        start_idx = end_idx = None
        diameter_km = 0.0
        if order:
            main = comps[order[0]]
            if len(main) >= 2:
                router = AngleBiasedRouter(x_f, y_f,
                                           angle_bias_m_per_rad=self.cfg.angle_bias_m_per_rad,
                                           step_penalty_m=self.cfg.step_penalty_m,
                                           min_edge_cost_m=self.cfg.min_edge_cost_m)
                s0 = main[0]
                dist0, prev0, bestprev0 = router.dijkstra(adj, s0)
                a = max(main, key=lambda i: dist0[i])
                dist_a, prev_a, bestprev_a = router.dijkstra(adj, a)
                b = max(main, key=lambda i: dist_a[i])
                penalized_cost_km = dist_a[b] / 1000.0  # for debug/inspection
                path_indices = router.reconstruct_path(prev_a, b, bestprev_a[b])
                start_idx, end_idx = a, b

                # Use *true* geometric length for display
                diameter_km = router.path_true_length_m(D_f, path_indices) / 1000.0

        # map
        m = self.map_builder.build(
            filtered=filtered,
            outliers=outliers,
            cluster_sizes=sizes,
            order=order,
            path_indices=path_indices,
            start_idx=start_idx,
            end_idx=end_idx,
            diameter_km=diameter_km,
            angle_bias_m_per_rad=self.cfg.angle_bias_m_per_rad,
            bounds_expand=self.cfg.bounds_expand,
        )

        if out_html is None:
            out_html = Path(file_path).with_suffix("").name + "_clusters_with_path_angle.html"
            out_html = Path(out_html)
        else:
            out_html = Path(out_html)
        m.save(str(out_html))
        return m, out_html
