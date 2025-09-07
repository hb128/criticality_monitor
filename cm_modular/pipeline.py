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
from .plotting import GraphPlotter

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

    # Graph plot (new)
    plot_graph: bool = False
    graph_cost_mode: str = "adj"  # "adj" or "geom"
    graph_out: str | None = None
    graph_figsize: tuple[float, float] = (9.0, 6.0)

class Pipeline:
    """End-to-end pipeline that fits a critical mass and extract its length."""
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

       # diameter path on largest component using *geometric* endpoint selection
        path_indices: list[int] = []
        start_idx = end_idx = None
        length_m = 0.0

        if order:
            # Take largest cluster
            main = comps[order[0]]
            if len(main) >= 2:
                router = AngleBiasedRouter(
                    x_f, y_f,
                    angle_bias_m_per_rad=self.cfg.angle_bias_m_per_rad,
                    step_penalty_m=self.cfg.step_penalty_m,
                    min_edge_cost_m=self.cfg.min_edge_cost_m
                )

                # 1) Build geometric-cost adjacency (same connectivity, weights = D_f)
                adj_geom = router.as_geometric_adjacency(adj, D_f)

                # 2) Find farthest pair under geometric distance (use plain geometry and no angle-bias to find real endpoints)
                # select first point (random)
                s0 = main[0]
                dist0, _ = router.dijkstra_plain(adj_geom, s0)
                # point furthest away from s0
                a = max(main, key=lambda i: dist0[i])
                # point furthest away from a
                dist_a, _ = router.dijkstra_plain(adj_geom, a)
                b = max(main, key=lambda i: dist_a[i])

                # 3) Compute *path* with penalized/angle-biased router
                _, prev_a, bestprev_a = router.dijkstra(adj, a)
                path_indices = router.reconstruct_path(prev_a, b, bestprev_a[b])
                start_idx, end_idx = a, b

                # 4) True geometric length for display
                length_m = router.path_true_length_m(D_f, path_indices)


        # Optional static graph plot (lon/lat positions)
        if self.cfg.plot_graph:
            # pick default output if not provided
            graph_out = self.cfg.graph_out
            # if graph_out is None:
            #     base = Path(file_path).with_suffix("").name
            #     graph_out = f"{base}_graph_{self.cfg.graph_cost_mode}.png"
            GraphPlotter.plot_graph(
                filtered=filtered,
                adj=adj,
                D_f=D_f,
                cost_mode=self.cfg.graph_cost_mode,
                path_indices=path_indices,
                router=locals().get("router", None),
                title=f"Graph ({self.cfg.graph_cost_mode} costs)",
                out=graph_out,
                figsize=self.cfg.graph_figsize,
            )

        # map
        m = self.map_builder.build(
            filtered=filtered,
            outliers=outliers,
            cluster_sizes=sizes,
            order=order,
            path_indices=path_indices,
            start_idx=start_idx,
            end_idx=end_idx,
            length_m=length_m,
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
