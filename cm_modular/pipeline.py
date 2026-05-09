from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
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
    """Configuration for the end-to-end pipeline.

    Provide either explicit bbox values or a ``city`` (string) referencing
    a preset in ``cm_modular.cities.CityPresets``.
    If ``city`` is supplied it overrides bbox parameters unless you also
    pass explicit lat_/lon_ values (those win).
    """
    city: str | None = None

    lat_min: float = 53.3
    lat_max: float = 53.8
    lon_min: float = 9.6
    lon_max: float = 10.35

    k: int = 10
    n_sigmas: float = 3.0

    L0: float = 50.0
    penalty_factor: float = 3.0

    angle_bias_m_per_rad: float = 8.0
    step_penalty_m: float = 5.0
    min_edge_cost_m: float = 15.0

    bounds_expand: float = 2.0

    plot_graph: bool = False
    graph_cost_mode: str = "adj"
    graph_out: str | None = None
    graph_figsize: tuple[float, float] = (9.0, 6.0)

    clustering_timespan_s: float | None = None
    path_timespan_s: float | None = None

    def __post_init__(self):
        if self.city:
            try:
                preset = CityPresets.get(self.city)
            except Exception as e:  # noqa: BLE001
                raise ValueError(str(e)) from e
            self.lat_min = preset.lat_min
            self.lat_max = preset.lat_max
            self.lon_min = preset.lon_min
            self.lon_max = preset.lon_max
        if self.clustering_timespan_s is not None and self.path_timespan_s is not None:
            if self.path_timespan_s > self.clustering_timespan_s:
                raise ValueError("path_timespan_s must be <= clustering_timespan_s")


@dataclass
class PipelineResult:
    """Typed result of one pipeline run.

    ``has_path`` is False when the input had fewer than ``max(10, k+1)`` points
    after bbox + timespan filtering (the early-exit branch).  All list/array
    fields are empty in that case; ``length_m`` is 0.0.
    """
    has_path: bool

    # Raw and filtered data
    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    hh: pd.DataFrame = field(default_factory=pd.DataFrame)
    filtered: pd.DataFrame = field(default_factory=pd.DataFrame)
    outliers: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Projected coordinates and distance matrix (inliers only)
    x_f: np.ndarray = field(default_factory=lambda: np.array([]))
    y_f: np.ndarray = field(default_factory=lambda: np.array([]))
    D_f: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))

    # Graph
    adj: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=int))
    radius_m: float = 0.0

    # Clustering
    comps: list = field(default_factory=list)
    sizes: np.ndarray = field(default_factory=lambda: np.array([]))
    order: list = field(default_factory=list)
    cluster_id: np.ndarray = field(default_factory=lambda: np.array([]))

    # Path
    path_df: Optional[pd.DataFrame] = None
    path_indices: list = field(default_factory=list)
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    length_m: float = 0.0
    router: Optional[object] = None
    segment_metrics: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage functions — each is a pure transformation, no IO, independently testable
# ---------------------------------------------------------------------------

def load_file_paths(
    file_paths: list[str | Path],
) -> pd.DataFrame:
    """Stage 1: Load all JSON log files into a single DataFrame."""
    if not file_paths:
        raise ValueError("No files provided to pipeline.")
    return DataLoader.load_multiple_locations_json(file_paths)


def bbox_filter(
    df: pd.DataFrame,
    cfg: PipelineConfig,
) -> pd.DataFrame:
    """Stage 2: Restrict rows to the configured bounding box."""
    return DataFilter.bbox(df, cfg.lat_min, cfg.lat_max, cfg.lon_min, cfg.lon_max)


def apply_timespan(
    df: pd.DataFrame,
    timespan_s: float | None,
) -> pd.DataFrame:
    """Stage 3 / 7: Keep only rows within ``timespan_s`` of the latest timestamp.

    If ``timespan_s`` is None or ``df`` is empty the original DataFrame is
    returned unchanged.
    """
    if timespan_s is None or df.empty:
        return df
    max_ts = df["timestamp"].max()
    min_ts = max_ts - timespan_s
    return df[df["timestamp"] >= min_ts].copy().reset_index(drop=True)


def project(
    df: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stage 3: Project lat/lon to planar metres and compute the distance matrix.

    Returns
    -------
    x, y : 1-D float arrays (planar coords, metres)
    D    : (n, n) symmetric float distance matrix
    """
    x, y = GeoUtils.deg2meters(df["lat"].to_numpy(), df["lon"].to_numpy())
    D = GeoUtils.pairwise_xy(x, y)
    return x, y, D


def knn_filter(
    df: pd.DataFrame,
    D: np.ndarray,
    cfg: PipelineConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, float]:
    """Stage 4: Remove spatial outliers with the robust KNN filter.

    Returns
    -------
    inliers, outliers : filtered DataFrames (reset index)
    D_filtered        : distance matrix restricted to inliers
    k_med             : median k-NN distance (used for graph radius)
    """
    keep, k_med = RobustKNNFilter.keep_by_knn(D, k=cfg.k, n_sigmas=cfg.n_sigmas)
    df = df.copy()
    df["keep"] = keep
    inliers = df[df["keep"]].copy().reset_index(drop=True)
    outliers = df[~df["keep"]].copy().reset_index(drop=True)
    idx = np.where(keep)[0]
    D_filtered = D[np.ix_(idx, idx)]
    return inliers, outliers, D_filtered, float(k_med)


def build_graph(
    D_f: np.ndarray,
    k_med: float,
    cfg: PipelineConfig,
) -> tuple[np.ndarray, float]:
    """Stage 5: Build the proximity graph from the filtered distance matrix.

    Returns
    -------
    adj      : adjacency list (list of lists of (neighbour, cost) tuples)
    radius_m : connection radius used
    """
    return GraphBuilder.build_graph(D_f, k_med, L0=cfg.L0, penalty_factor=cfg.penalty_factor)


def cluster(
    adj: np.ndarray,
) -> tuple[list, np.ndarray, list, np.ndarray]:
    """Stage 6: Assign cluster IDs to nodes via connected-components DFS.

    Returns
    -------
    comps, sizes, order, cluster_id — same as ``Clusterer.assign_from_components``
    """
    return Clusterer.assign_from_components(adj)


def find_diameter(
    adj: np.ndarray,
    D_f: np.ndarray,
    x_f: np.ndarray,
    y_f: np.ndarray,
    main_indices: list[int],
    cfg: PipelineConfig,
) -> tuple[list[int], float, list[dict], Optional[object], Optional[int], Optional[int]]:
    """Stage 8: Find the geometric diameter path through the largest cluster.

    Parameters
    ----------
    main_indices : candidate node indices for path endpoints (subset of the
                   largest component, already timespan-filtered).

    Returns
    -------
    path_indices    : node indices along the diameter path
    length_m        : true geometric path length in metres
    segment_metrics : list of per-segment dicts
    router          : the ``AngleBiasedRouter`` instance (or None)
    start_idx       : first endpoint index (or None)
    end_idx         : second endpoint index (or None)
    """
    if len(main_indices) < 2:
        return [], 0.0, [], None, None, None

    router = AngleBiasedRouter(
        x_f, y_f,
        angle_bias_m_per_rad=cfg.angle_bias_m_per_rad,
        step_penalty_m=cfg.step_penalty_m,
        min_edge_cost_m=cfg.min_edge_cost_m,
    )

    adj_geom = router.as_geometric_adjacency(adj, D_f)
    s0 = main_indices[0]
    dist0, _ = router.dijkstra_plain(adj_geom, s0)
    a = max(main_indices, key=lambda i: dist0[i])
    dist_a, _ = router.dijkstra_plain(adj_geom, a)
    b = max(main_indices, key=lambda i: dist_a[i])

    _, prev_a, bestprev_a = router.dijkstra(adj, a)
    path_indices = router.reconstruct_path(prev_a, b, bestprev_a[b])
    length_m = router.path_true_length_m(D_f, path_indices)

    segment_metrics: list[dict] = []
    for i in range(len(path_indices) - 1):
        idx_start = path_indices[i]
        idx_stop = path_indices[i + 1]
        geo_len = float(D_f[idx_start, idx_stop])
        angle_bias = GraphBuilder.angle_bias_for_segment(x_f, y_f, path_indices, i)
        segment_metrics.append(
            {"start": idx_start, "stop": idx_stop, "geo_len": geo_len, "angle_len": geo_len * angle_bias}
        )

    return path_indices, length_m, segment_metrics, router, a, b


def collect_metrics(
    result: PipelineResult,
    cfg: PipelineConfig,
    file_paths: list[str | Path],
    out_html_path: Path,
) -> dict:
    """Stage 9: Assemble the flat metrics dict from a ``PipelineResult``."""
    r = result
    return {
        "n_points": int(len(r.df)),
        "n_bbox": int(len(r.hh)),
        "n_filtered": int(len(r.filtered)),
        "largest_comp_size": int(r.sizes[r.order[0]]) if r.order else 0,
        "connection_radius_m": float(r.radius_m),
        "length_m": float(r.length_m),
        "angle_bias_m_per_rad": float(cfg.angle_bias_m_per_rad),
        "L0_m": float(cfg.L0),
        "penalty_factor": float(cfg.penalty_factor),
        "city": cfg.city,
        "clustering_timespan_s": cfg.clustering_timespan_s,
        "path_timespan_s": cfg.path_timespan_s,
        "files": [str(f) for f in file_paths],
        "html": str(out_html_path),
    }

def _early_exit(df: pd.DataFrame, hh: pd.DataFrame, clustering_df: pd.DataFrame) -> PipelineResult:
    """Return a has_path=False result for under-populated inputs."""
    n = len(clustering_df)
    filtered = clustering_df.copy().assign(keep=True, cluster=np.zeros(n, dtype=int)) if n > 0 \
            else clustering_df.copy()
    filtered = filtered.reset_index(drop=True)
    x_f, y_f = (GeoUtils.deg2meters(filtered["lat"].to_numpy(), filtered["lon"].to_numpy())
                if n > 0 else (np.array([]), np.array([])))
    return PipelineResult(
        has_path=False,
        df=df, hh=hh, filtered=filtered,
        outliers=clustering_df.iloc[0:0].copy().reset_index(drop=True),
        x_f=x_f, y_f=y_f, D_f=np.zeros((n, n)),
        adj=np.zeros((n, n), dtype=int), radius_m=0.0,
        comps=[list(range(n))] if n > 0 else [],
        sizes=np.array([n]) if n > 0 else np.array([]),
        order=[0] if n > 0 else [],
        cluster_id=np.zeros(n, dtype=int) if n > 0 else np.array([]),
    )

# ---------------------------------------------------------------------------
# Pipeline class — thin compositor
# ---------------------------------------------------------------------------

class Pipeline:
    """End-to-end pipeline: thin compositor over the stage functions above."""

    def __init__(self, cfg: PipelineConfig | None = None):
        self.cfg = cfg or PipelineConfig()
        self.map_builder = MapBuilder()
        self.file_paths: list[str | Path] = []

    def add_files(self, file_paths: list[str | Path]):
        """Add more files to the pipeline."""
        self.file_paths.extend(file_paths)

    def _compute(self) -> PipelineResult:
        cfg = self.cfg

        df = load_file_paths(self.file_paths)
        hh = bbox_filter(df, cfg)
        clustering_df = apply_timespan(hh, cfg.clustering_timespan_s)

        if len(clustering_df) < max(10, cfg.k + 1):
            return _early_exit(df, hh, clustering_df)

        _, _, D = project(clustering_df)
        inliers, outliers, D_f, k_med = knn_filter(clustering_df, D, cfg)
        x_f, y_f = GeoUtils.deg2meters(inliers["lat"].to_numpy(), inliers["lon"].to_numpy())
        adj, radius_m = build_graph(D_f, k_med, cfg)
        comps, sizes, order, cluster_id = cluster(adj)
        filtered = inliers.assign(cluster=cluster_id)
        path_df = apply_timespan(filtered, cfg.path_timespan_s)

        path_indices, length_m, segment_metrics, router, start_idx, end_idx = (
            find_diameter(adj, D_f, x_f, y_f,
                        [i for i in comps[order[0]] if i in set(path_df.index)], cfg)
            if order else ([], 0.0, [], None, None, None)
        )

        return PipelineResult(
            has_path=bool(path_indices),
            df=df, hh=hh, filtered=filtered, outliers=outliers,
            x_f=x_f, y_f=y_f, D_f=D_f, adj=adj, radius_m=radius_m,
            comps=comps, sizes=sizes, order=order, cluster_id=cluster_id,
            path_df=path_df, path_indices=path_indices,
            start_idx=start_idx, end_idx=end_idx,
            length_m=length_m, router=router, segment_metrics=segment_metrics,
        )

    def run(self, out_html: str | Path | None = None, return_metrics: bool = False):
        """Execute full pipeline and save a Folium map to HTML."""
        res = self._compute()

        if self.cfg.plot_graph:
            GraphPlotter.plot_graph(
                filtered=res.filtered,
                adj=res.adj,
                D_f=res.D_f,
                cost_mode=self.cfg.graph_cost_mode,
                path_indices=res.path_indices,
                router=res.router,
                title=f"Graph ({self.cfg.graph_cost_mode} costs)",
                out=self.cfg.graph_out,
                figsize=self.cfg.graph_figsize,
            )

        m = self.map_builder.build(
            filtered=res.filtered,
            outliers=res.outliers,
            path_indices=res.path_indices,
            bounds_expand=self.cfg.bounds_expand,
            path_df=res.path_df,
            segment_metrics=res.segment_metrics,
        )

        first_file = self.file_paths[0] if self.file_paths else "output"
        if out_html is None:
            out_html_path = Path(Path(first_file).with_suffix("").name + ".html")
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

        if return_metrics:
            return m, out_html_path, collect_metrics(res, self.cfg, self.file_paths, out_html_path)
        return m, out_html_path

    def run_with_metrics(self, out_html: str | Path | None = None):
        """Like run(), but also returns a metrics dict for batch processing."""
        return self.run(out_html=out_html, return_metrics=True)