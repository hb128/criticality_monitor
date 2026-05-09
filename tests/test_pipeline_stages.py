"""Unit tests for the Phase 4 stage functions extracted from _compute().

All tests are pure (no filesystem, no network).  They import individual stage
functions and verify that each one satisfies its contract in isolation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cm_modular.pipeline import (
    PipelineConfig,
    PipelineResult,
    apply_timespan,
    bbox_filter,
    build_graph,
    cluster,
    collect_metrics,
    find_diameter,
    knn_filter,
    project,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hamburg_df():
    """10 points tightly clustered near Hamburg centre — no outliers."""
    rng = np.random.default_rng(42)
    lat0, lon0 = 53.55, 10.01
    n = 10
    lats = lat0 + rng.normal(0, 0.001, n)
    lons = lon0 + rng.normal(0, 0.001, n)
    return pd.DataFrame({
        "id": [str(i) for i in range(n)],
        "lat": lats,
        "lon": lons,
        "timestamp": np.arange(n, dtype=float),
    })


@pytest.fixture
def hamburg_df_with_outlier(hamburg_df):
    """Same cluster plus one point 50 km away."""
    outlier = pd.DataFrame({"id": ["outlier"], "lat": [54.05], "lon": [10.8], "timestamp": [99.0]})
    return pd.concat([hamburg_df, outlier], ignore_index=True)


@pytest.fixture
def default_cfg():
    # k=4 keeps kth index within bounds for the 10-point hamburg_df fixture
    return PipelineConfig(city="hamburg", k=4)


# ---------------------------------------------------------------------------
# bbox_filter
# ---------------------------------------------------------------------------

class TestBboxFilter:
    def test_keeps_points_inside_bbox(self, hamburg_df, default_cfg):
        result = bbox_filter(hamburg_df, default_cfg)
        assert len(result) == len(hamburg_df)

    def test_removes_point_outside_bbox(self, hamburg_df_with_outlier, default_cfg):
        result = bbox_filter(hamburg_df_with_outlier, default_cfg)
        # The outlier at lat=54.05 is above lat_max=53.8
        assert len(result) == len(hamburg_df_with_outlier) - 1

    def test_empty_input_returns_empty(self, default_cfg):
        empty = pd.DataFrame(columns=["id", "lat", "lon", "timestamp"])
        result = bbox_filter(empty, default_cfg)
        assert result.empty


# ---------------------------------------------------------------------------
# apply_timespan
# ---------------------------------------------------------------------------

class TestApplyTimespan:
    def test_none_returns_original(self, hamburg_df):
        result = apply_timespan(hamburg_df, None)
        assert len(result) == len(hamburg_df)

    def test_timespan_keeps_recent_rows(self, hamburg_df):
        # timestamps 0..9; keep last 5 seconds → rows with timestamp >= 4.0
        result = apply_timespan(hamburg_df, 5.0)
        assert len(result) == 6
        assert result["timestamp"].min() >= 4.0

    def test_empty_df_returns_empty(self):
        empty = pd.DataFrame(columns=["id", "lat", "lon", "timestamp"])
        result = apply_timespan(empty, 60.0)
        assert result.empty

    def test_large_timespan_keeps_all(self, hamburg_df):
        result = apply_timespan(hamburg_df, 1_000_000.0)
        assert len(result) == len(hamburg_df)


# ---------------------------------------------------------------------------
# project
# ---------------------------------------------------------------------------

class TestProject:
    def test_distance_matrix_is_symmetric(self, hamburg_df):
        x, y, D = project(hamburg_df)
        assert np.allclose(D, D.T)

    def test_distance_matrix_diagonal_is_zero(self, hamburg_df):
        _, _, D = project(hamburg_df)
        assert np.allclose(np.diag(D), 0.0)

    def test_output_shapes_match(self, hamburg_df):
        n = len(hamburg_df)
        x, y, D = project(hamburg_df)
        assert x.shape == (n,)
        assert y.shape == (n,)
        assert D.shape == (n, n)

    def test_known_distance(self):
        """Two points ~111 km apart on the same meridian."""
        df = pd.DataFrame({"lat": [0.0, 1.0], "lon": [0.0, 0.0], "timestamp": [0, 1]})
        _, _, D = project(df)
        # 1 degree latitude ≈ 111_195 m
        assert abs(D[0, 1] - 111_195) < 500


# ---------------------------------------------------------------------------
# knn_filter
# ---------------------------------------------------------------------------

class TestKnnFilter:
    def test_outlier_is_removed(self, hamburg_df_with_outlier):
        # Use a wide bbox so the geographic outlier passes bbox but fails KNN
        wide_cfg = PipelineConfig(lat_min=50.0, lat_max=56.0, lon_min=8.0, lon_max=12.0, k=4)
        _, _, D = project(hamburg_df_with_outlier)
        inliers, outliers, D_f, k_med = knn_filter(hamburg_df_with_outlier, D, wide_cfg)
        assert "outlier" in outliers["id"].values
        assert "outlier" not in inliers["id"].values

    def test_D_f_shape_matches_inliers(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        inliers, _, D_f, _ = knn_filter(hamburg_df, D, default_cfg)
        n = len(inliers)
        assert D_f.shape == (n, n)

    def test_D_f_is_symmetric(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        _, _, D_f, _ = knn_filter(hamburg_df, D, default_cfg)
        assert np.allclose(D_f, D_f.T)

    def test_k_med_is_positive(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        _, _, _, k_med = knn_filter(hamburg_df, D, default_cfg)
        assert k_med > 0.0


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_returns_adj_and_radius(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        inliers, _, D_f, k_med = knn_filter(hamburg_df, D, default_cfg)
        adj, radius_m = build_graph(D_f, k_med, default_cfg)
        assert radius_m > 0.0
        assert len(adj) == len(inliers)

    def test_no_self_loops(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        _, _, D_f, k_med = knn_filter(hamburg_df, D, default_cfg)
        adj, _ = build_graph(D_f, k_med, default_cfg)
        for i, neighbours in enumerate(adj):
            assert all(j != i for j, _ in neighbours)


# ---------------------------------------------------------------------------
# cluster
# ---------------------------------------------------------------------------

class TestCluster:
    def test_all_same_cluster_for_dense_input(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        _, _, D_f, k_med = knn_filter(hamburg_df, D, default_cfg)
        adj, _ = build_graph(D_f, k_med, default_cfg)
        comps, sizes, order, cluster_id = cluster(adj)
        assert sizes[order[0]] == max(sizes)

    def test_cluster_ids_assigned_to_all_nodes(self, hamburg_df, default_cfg):
        n = len(hamburg_df)
        _, _, D = project(hamburg_df)
        inliers, _, D_f, k_med = knn_filter(hamburg_df, D, default_cfg)
        adj, _ = build_graph(D_f, k_med, default_cfg)
        _, _, _, cluster_id = cluster(adj)
        assert len(cluster_id) == len(inliers)


# ---------------------------------------------------------------------------
# find_diameter
# ---------------------------------------------------------------------------

def _x_y(df):
    from cm_modular.geo import GeoUtils
    return GeoUtils.deg2meters(df["lat"].to_numpy(), df["lon"].to_numpy())


class TestFindDiameter:
    def test_returns_empty_for_single_candidate(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        _, _, D_f, k_med = knn_filter(hamburg_df, D, default_cfg)
        adj, _ = build_graph(D_f, k_med, default_cfg)
        x_f = np.zeros(len(D_f))
        y_f = np.zeros(len(D_f))
        path, length, segs, router, s, e = find_diameter(adj, D_f, x_f, y_f, [0], default_cfg)
        assert path == []
        assert length == 0.0

    def test_path_length_positive_for_cluster(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        inliers, _, D_f, k_med = knn_filter(hamburg_df, D, default_cfg)
        adj, _ = build_graph(D_f, k_med, default_cfg)
        x_f, y_f = _x_y(inliers)
        comps, sizes, order, _ = cluster(adj)
        main_indices = comps[order[0]]
        path, length, segs, router, s, e = find_diameter(adj, D_f, x_f, y_f, main_indices, default_cfg)
        assert len(path) >= 2
        assert length > 0.0

    def test_segment_count_matches_path_edges(self, hamburg_df, default_cfg):
        _, _, D = project(hamburg_df)
        inliers, _, D_f, k_med = knn_filter(hamburg_df, D, default_cfg)
        adj, _ = build_graph(D_f, k_med, default_cfg)
        x_f, y_f = _x_y(inliers)
        comps, sizes, order, _ = cluster(adj)
        main_indices = comps[order[0]]
        path, _, segs, _, _, _ = find_diameter(adj, D_f, x_f, y_f, main_indices, default_cfg)
        assert len(segs) == max(0, len(path) - 1)


# ---------------------------------------------------------------------------
# PipelineResult early-exit
# ---------------------------------------------------------------------------

class TestPipelineResult:
    def test_has_path_false_defaults_empty(self):
        result = PipelineResult(has_path=False)
        assert not result.has_path
        assert result.length_m == 0.0
        assert result.path_indices == []

    def test_has_path_true_stores_values(self):
        result = PipelineResult(has_path=True, path_indices=[0, 1, 2], length_m=42.0)
        assert result.has_path
        assert result.length_m == 42.0


# ---------------------------------------------------------------------------
# collect_metrics
# ---------------------------------------------------------------------------

class TestCollectMetrics:
    def test_all_expected_keys_present(self, tmp_path, default_cfg):
        out = tmp_path / "out.html"
        result = PipelineResult(
            has_path=False,
            df=pd.DataFrame({"a": [1]}),
            hh=pd.DataFrame({"a": [1]}),
            filtered=pd.DataFrame({"a": []}),
            sizes=np.array([]),
            order=[],
            radius_m=0.0,
            length_m=0.0,
        )
        m = collect_metrics(result, default_cfg, ["dummy.json"], out)
        for key in ("n_points", "n_bbox", "n_filtered", "length_m", "html", "files"):
            assert key in m

    def test_html_path_matches(self, tmp_path, default_cfg):
        out = tmp_path / "test.html"
        result = PipelineResult(
            has_path=False,
            df=pd.DataFrame(),
            hh=pd.DataFrame(),
            filtered=pd.DataFrame(),
            sizes=np.array([]),
            order=[],
        )
        m = collect_metrics(result, default_cfg, [], out)
        assert m["html"] == str(out)