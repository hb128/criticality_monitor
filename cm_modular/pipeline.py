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

from .cities import CityPresets


@dataclass
class PipelineConfig:
    """Configuration for the end‑to‑end pipeline.

    Provide either explicit bbox values or a ``city`` (string) referencing
    a preset in ``cm_modular.cities.CityPresets``.
    If ``city`` is supplied it overrides bbox parameters unless you also
    pass explicit lat_/lon_ values (those win).
    """
    # City name (optional). If provided and bbox not explicitly overridden
    # we fill in from preset during ``__post_init__``.
    city: str | None = None

    # BBox defaults (Hamburg – same as previous behaviour)
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

    # Timespan (seconds) for clustering and path length
    clustering_timespan_s: float | None = None  # If set, only use points within this timespan for clustering
    path_timespan_s: float | None = None  # If set, only use points within this timespan for path length (<= clustering_timespan_s)

    def __post_init__(self):
        # Always apply city preset if provided (unconditional override)
        if self.city:
            try:
                preset = CityPresets.get(self.city)
            except Exception as e:  # noqa: BLE001
                raise ValueError(str(e)) from e
            self.lat_min = preset.lat_min
            self.lat_max = preset.lat_max
            self.lon_min = preset.lon_min
            self.lon_max = preset.lon_max
        # Ensure path_timespan_s <= clustering_timespan_s if both set
        if self.clustering_timespan_s is not None and self.path_timespan_s is not None:
            if self.path_timespan_s > self.clustering_timespan_s:
                raise ValueError("path_timespan_s must be <= clustering_timespan_s")

class Pipeline:
    """End-to-end pipeline that fits a critical mass and extract its length."""
    def __init__(self, cfg: PipelineConfig | None = None):
        self.cfg = cfg or PipelineConfig()
        self.map_builder = MapBuilder()
        self.file_paths: list[str | Path] = []

    def add_files(self, file_paths: list[str | Path]):
        """Add more files to the pipeline."""
        self.file_paths.extend(file_paths)

    def _compute(self):
        """Run the data processing steps and return intermediates + metrics."""
        # Load all files
        if not self.file_paths:
            raise ValueError("No files provided to pipeline.")
        df = DataLoader.load_multiple_locations_json(self.file_paths)

        # bbox filter
        hh = DataFilter.bbox(df, self.cfg.lat_min, self.cfg.lat_max, self.cfg.lon_min, self.cfg.lon_max)

        # Timespan filtering for clustering
        clustering_df = hh
        if self.cfg.clustering_timespan_s is not None and not hh.empty:
            max_ts = hh["timestamp"].max()
            min_ts = max_ts - self.cfg.clustering_timespan_s
            clustering_df = hh[hh["timestamp"] >= min_ts].copy().reset_index(drop=True)

        # Early exit for small sample sizes BEFORE KNN filtering / graphing.
        if len(clustering_df) < 10:
            print(f"Points in bbox (clustering timespan): {len(clustering_df)}")
            n = len(clustering_df)
            clustering_df = clustering_df.copy()
            clustering_df["keep"] = True  # mark all as kept for consistency
            filtered = clustering_df.copy().reset_index(drop=True)
            outliers = clustering_df.iloc[0:0].copy().reset_index(drop=True)
            # Geometry
            if n > 0:
                x_f, y_f = GeoUtils.deg2meters(filtered["lat"].to_numpy(), filtered["lon"].to_numpy())
            else:
                x_f = np.array([])
                y_f = np.array([])
            D_f = np.zeros((n, n), dtype=float)
            adj = np.zeros((n, n), dtype=int)
            radius_m = 0.0
            if n > 0:
                comps = [list(range(n))]
                sizes = np.array([n])
                order = [0]
                cluster_id = np.zeros(n, dtype=int)
                filtered = filtered.copy()
                filtered["cluster"] = cluster_id
            else:
                comps = []
                sizes = np.array([])
                order = []
                cluster_id = np.array([])
            path_indices: list[int] = []
            path_df: pd.DataFrame | None = None
            start_idx = None
            end_idx = None
            length_m = 0.0
            router = None
            return {
                "df": df,
                "hh": hh,
                "filtered": filtered,
                "outliers": outliers,
                "x_f": x_f,
                "y_f": y_f,
                "D_f": D_f,
                "adj": adj,
                "radius_m": radius_m,
                "comps": comps,
                "sizes": sizes,
                "order": order,
                "cluster_id": cluster_id,
                "path_indices": path_indices,
                "start_idx": start_idx,
                "end_idx": end_idx,
                "length_m": length_m,
                "router": router,
                "path_df": path_df,
            }

        # base geometry + KNN filter
        x, y = GeoUtils.deg2meters(clustering_df["lat"].to_numpy(), clustering_df["lon"].to_numpy())
        D = GeoUtils.pairwise_xy(x, y)
        keep, k_med = RobustKNNFilter.keep_by_knn(D, k=self.cfg.k, n_sigmas=self.cfg.n_sigmas)
        clustering_df = clustering_df.copy()
        clustering_df["keep"] = keep
        filtered = clustering_df[clustering_df["keep"]].copy().reset_index(drop=True)
        outliers = clustering_df[~clustering_df["keep"]].copy().reset_index(drop=True)

        # graph on filtered
        x_f, y_f = GeoUtils.deg2meters(filtered["lat"].to_numpy(), filtered["lon"].to_numpy())
        D_f = GeoUtils.pairwise_xy(x_f, y_f)
        adj, radius_m = GraphBuilder.build_graph(D_f, k_med, L0=self.cfg.L0, penalty_factor=self.cfg.penalty_factor)

        # cluster ids
        comps, sizes, order, cluster_id = Clusterer.assign_from_components(adj)
        filtered = filtered.copy()
        filtered["cluster"] = cluster_id

        # Timespan filtering for path length
        path_df = filtered
        if self.cfg.path_timespan_s is not None and not filtered.empty:
            max_ts = filtered["timestamp"].max()
            min_ts = max_ts - self.cfg.path_timespan_s
            path_df = filtered[filtered["timestamp"] >= min_ts].copy().reset_index(drop=True)


        # diameter path on largest component using geometric endpoint selection
        path_indices: list[int] = []
        start_idx = end_idx = None
        length_m = 0.0
        router = None
        if order:
            main = comps[order[0]]
            # Only consider indices in path_df for path endpoints, but keep full graph
            path_df_indices_set = set(path_df.index)
            main_path_indices = [i for i in main if i in path_df_indices_set]
            if len(main_path_indices) >= 2:
                router = AngleBiasedRouter(
                    x_f, y_f,
                    angle_bias_m_per_rad=self.cfg.angle_bias_m_per_rad,
                    step_penalty_m=self.cfg.step_penalty_m,
                    min_edge_cost_m=self.cfg.min_edge_cost_m
                )

                # 1) Build geometric-cost adjacency (same connectivity, weights = D_f)
                adj_geom = router.as_geometric_adjacency(adj, D_f)
                # 2) Find farthest pair under geometric distance (plain geometry, no angle-bias)
                s0 = main_path_indices[0]
                dist0, _ = router.dijkstra_plain(adj_geom, s0)
                a = max(main_path_indices, key=lambda i: dist0[i])
                dist_a, _ = router.dijkstra_plain(adj_geom, a)
                b = max(main_path_indices, key=lambda i: dist_a[i])
                # print(f"Selected endpoints (by geometric dist): {a} (dist: {dist0[a]}) - {b} (dist: {dist_a[b]})")

                # 3) Compute path with penalized/angle-biased router (on adjacency 'adj')
                _, prev_a, bestprev_a = router.dijkstra(adj, a)
                path_indices = router.reconstruct_path(prev_a, b, bestprev_a[b])
                start_idx, end_idx = a, b
                # 4) True geometric length for display/metrics
                length_m = router.path_true_length_m(D_f, path_indices)
        else:
            # no components (all filtered out)
            path_indices = []
            start_idx = end_idx = None
            length_m = 0.0
            router = None
        return {
            "df": df,
            "hh": hh,
            "filtered": filtered,
            "outliers": outliers,
            "x_f": x_f,
            "y_f": y_f,
            "D_f": D_f,
            "adj": adj,
            "radius_m": radius_m,
            "comps": comps,
            "sizes": sizes,
            "order": order,
            "cluster_id": cluster_id,
            "path_indices": path_indices,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "length_m": length_m,
            "router": router,
            "path_df": path_df,
        }


    def run(self, out_html: str | Path | None = None):
        """Execute full pipeline and save a Folium map to HTML.

        Parameters
        ----------
        out_html : str | Path | None
            Output HTML file. If None, writes next to first file with a default name.

        Returns
        -------
        (m, out_path) : (folium.Map, Path)
        """
        res = self._compute()
        filtered = res["filtered"]
        outliers = res["outliers"]
        D_f = res["D_f"]
        adj = res["adj"]
        sizes = res["sizes"]
        order = res["order"]
        path_indices = res["path_indices"]
        start_idx = res["start_idx"]
        end_idx = res["end_idx"]
        length_m = res["length_m"]
        router = res["router"]

        # Optional static graph plot (lon/lat positions)
        if self.cfg.plot_graph:
            graph_out = self.cfg.graph_out
            GraphPlotter.plot_graph(
                filtered=filtered,
                adj=adj,
                D_f=D_f,
                cost_mode=self.cfg.graph_cost_mode,
                path_indices=path_indices,
                router=router,
                title=f"Graph ({self.cfg.graph_cost_mode} costs)",
                out=graph_out,
                figsize=self.cfg.graph_figsize,
            )

        # Use path_df from res for highlighting
        m = self.map_builder.build(
            filtered=filtered,
            outliers=outliers,
            path_indices=path_indices,
            bounds_expand=self.cfg.bounds_expand,
            path_df=res["path_df"]
        )

        # Use first file for default output name
        first_file = self.file_paths[0] if self.file_paths else "output"
        if out_html is None:
            out_html = Path(first_file).with_suffix("").name + ".html"
            out_html = Path(out_html)
        else:
            out_html = Path(out_html)
            base_stem = Path(first_file).with_suffix("").name
            default_filename = base_stem + ".html"
            if out_html.exists() and out_html.is_dir():
                out_html = out_html / default_filename
            elif out_html.suffix == "":
                out_html.mkdir(parents=True, exist_ok=True)
                out_html = out_html / default_filename
            else:
                out_html.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(out_html))
        return m, out_html

    def run_with_metrics(self, out_html: str | Path | None = None):
        """Like run(), but also returns a metrics dict for batch processing."""
        res = self._compute()

        # Use path_df from res for highlighting
        m = self.map_builder.build(
            filtered=res["filtered"],
            outliers=res["outliers"],
            path_indices=res["path_indices"],
            bounds_expand=self.cfg.bounds_expand,
            path_df=res["path_df"]
        )

        first_file = self.file_paths[0] if self.file_paths else "output"
        if out_html is None:
            out_html_path = Path(first_file).with_suffix("").name + ".html"
            out_html_path = Path(out_html_path)
        else:
            out_html_path = Path(out_html)
            base_stem = Path(first_file).with_suffix("").name
            default_filename = base_stem + ".html"
            if out_html_path.exists() and out_html_path.is_dir():
                out_html_path = out_html_path / default_filename
            elif out_html_path.suffix == "":
                out_html_path.mkdir(parents=True, exist_ok=True)
                out_html_path = out_html_path / default_filename
            else:
                out_html_path.parent.mkdir(parents=True, exist_ok=True)

        m.save(str(out_html_path))

        df = res["df"]
        hh = res["hh"]
        filtered = res["filtered"]
        sizes = res["sizes"]
        order = res["order"]
        metrics = {
            "n_points": int(len(df)),
            "n_bbox": int(len(hh)),
            "n_filtered": int(len(filtered)),
            "largest_comp_size": int(sizes[order[0]]) if order else 0,
            "connection_radius_m": float(res["radius_m"]),
            "length_m": float(res["length_m"]),
            "angle_bias_m_per_rad": float(self.cfg.angle_bias_m_per_rad),
            "L0_m": float(self.cfg.L0),
            "penalty_factor": float(self.cfg.penalty_factor),
            "city": self.cfg.city,  # Add city from config
            "clustering_timespan_s": self.cfg.clustering_timespan_s,
            "path_timespan_s": self.cfg.path_timespan_s,
            "files": [str(f) for f in self.file_paths],
        }

        metrics_with_paths = {
            **metrics,
            "html": str(out_html_path),
        }

        return m, out_html_path, metrics_with_paths
