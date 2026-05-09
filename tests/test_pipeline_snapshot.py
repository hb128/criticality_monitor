from pathlib import Path

import pytest

from cm_modular.pipeline import PipelineConfig, Pipeline
from cm_modular.io import DataLoader
from cm_modular.filtering import DataFilter, RobustKNNFilter
from cm_modular.geo import GeoUtils
from cm_modular.graphing import GraphBuilder
from cm_modular.clustering import Clusterer


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fixture_path() -> Path:
    """Full-run fixture: small Hamburg ride."""
    return Path("tests/fixtures/hamburg_ride_small.json")


@pytest.fixture
def sparse_fixture_path() -> Path:
    """Sparse fixture: triggers early-exit branch in compute."""
    return Path("tests/fixtures/hamburg_ride_sparse.json")


# --- Small helpers per stage ------------------------------------------------


def load_raw_df(fixture_path: Path):
    return DataLoader.load_multiple_locations_json([str(fixture_path)])


def apply_bbox(df, config: PipelineConfig):
    lat_min, lat_max = config.lat_min, config.lat_max
    lon_min, lon_max = config.lon_min, config.lon_max
    return DataFilter.bbox(df, lat_min, lat_max, lon_min, lon_max)


def project_and_distance(df_bbox):
    x, y = GeoUtils.deg2meters(df_bbox["lat"].to_numpy(), df_bbox["lon"].to_numpy())
    D = GeoUtils.pairwise_xy(x, y)
    return x, y, D


def apply_knn(D, config: PipelineConfig):
    keep, kmed = RobustKNNFilter.keep_by_knn(D, k=config.k, n_sigmas=config.n_sigmas)
    return keep, kmed


def build_graph(D, keep, kmed, config: PipelineConfig):
    D_filtered = D[keep][:, keep]
    adj, radius_m = GraphBuilder.build_graph(
        D_filtered,
        k_med=kmed,
        L0=config.L0,
        penalty_factor=config.penalty_factor,
    )
    return adj, radius_m


# --- End-to-end snapshot tests ---------------------------------------------


def test_snapshot_full_run(tmp_path: Path, fixture_path: Path) -> None:
    config = PipelineConfig(city="hamburg")
    pipeline = Pipeline(config)
    pipeline.add_files([str(fixture_path)])

    out_html = tmp_path / "out.html"

    # Unpack: map object, html path, metrics dict
    _folium_map, html_path, metrics = pipeline.run(
        out_html=str(out_html),
        return_metrics=True,
    )

    # Basic sanity checks
    assert html_path == out_html
    assert out_html.exists()

    EXPECTED = {
        "n_points": 446,
        "n_bbox": 109,
        "n_filtered": 74,
        "largest_comp_size": 72,
        "connection_radius_m": 252.06963512656085,
        "length_m": 1415.2277761873506,
    }

    for key in EXPECTED:
        assert key in metrics

    assert metrics["n_points"] == EXPECTED["n_points"]
    assert metrics["n_bbox"] == EXPECTED["n_bbox"]
    assert metrics["n_filtered"] == EXPECTED["n_filtered"]
    assert metrics["largest_comp_size"] == EXPECTED["largest_comp_size"]

    assert metrics["connection_radius_m"] == pytest.approx(EXPECTED["connection_radius_m"], rel=1e-3)  # 0.1%
    assert metrics["length_m"] == pytest.approx(EXPECTED["length_m"], rel=1e-3)  # 0.1%


def test_sparse_input_does_not_crash(tmp_path: Path, sparse_fixture_path: Path) -> None:
    config = PipelineConfig(city="hamburg")
    pipeline = Pipeline(config)
    pipeline.add_files([str(sparse_fixture_path)])

    out_html = tmp_path / "out.html"

    _folium_map, html_path, metrics = pipeline.run(
        out_html=str(out_html),
        return_metrics=True,
    )

    assert html_path == out_html
    assert out_html.exists()

    assert metrics["length_m"] == 0.0
    assert metrics["n_filtered"] == 9


# --- Per-stage integration snapshots ---------------------------------------


def test_dataloader_snapshot(fixture_path: Path) -> None:
    df = load_raw_df(fixture_path)

    EXPECTED_N_ROWS = 446
    EXPECTED_COLUMNS = ["id", "lat", "lon", "timestamp"]
    EXPECTED_FIRST_TS = 1758915587

    assert df.shape[0] == EXPECTED_N_ROWS
    assert list(df.columns) == EXPECTED_COLUMNS

    first_ts = df["timestamp"].iloc[0]
    assert first_ts == EXPECTED_FIRST_TS


def test_bbox_snapshot(fixture_path: Path) -> None:
    df = load_raw_df(fixture_path)
    config = PipelineConfig(city="hamburg")

    filtered = apply_bbox(df, config)

    EXPECTED_N_BBOX = 109
    assert filtered.shape[0] == EXPECTED_N_BBOX

    assert (filtered["lat"] >= config.lat_min).all()
    assert (filtered["lat"] <= config.lat_max).all()
    assert (filtered["lon"] >= config.lon_min).all()
    assert (filtered["lon"] <= config.lon_max).all()


def test_projection_and_distance_snapshot(fixture_path: Path) -> None:
    df = load_raw_df(fixture_path)
    config = PipelineConfig(city="hamburg")
    df_bbox = apply_bbox(df, config)

    _x, _y, D = project_and_distance(df_bbox)

    EXPECTED_N = 109
    assert D.shape == (EXPECTED_N, EXPECTED_N)

    D_min = float(D.min())
    D_max = float(D.max())

    EXPECTED_D_MIN = 0.0
    EXPECTED_D_MAX = 30623.366649973337

    assert abs(D_min - EXPECTED_D_MIN) < 1e-9
    assert abs(D_max - EXPECTED_D_MAX) < 1e-9


def test_knn_filter_snapshot(fixture_path: Path) -> None:
    df = load_raw_df(fixture_path)
    config = PipelineConfig(city="hamburg")
    df_bbox = apply_bbox(df, config)
    _x, _y, D = project_and_distance(df_bbox)

    keep, kmed = apply_knn(D, config)

    EXPECTED_N_FILTERED = 74
    assert keep.sum() == EXPECTED_N_FILTERED

    EXPECTED_KMED = 157.54352195410053
    assert abs(float(kmed) - EXPECTED_KMED) < 1e-9


def test_graph_builder_snapshot(fixture_path: Path) -> None:
    df = load_raw_df(fixture_path)
    config = PipelineConfig(city="hamburg")
    df_bbox = apply_bbox(df, config)
    _x, _y, D = project_and_distance(df_bbox)
    keep, kmed = apply_knn(D, config)

    df_inliers = df_bbox.loc[keep].reset_index(drop=True)
    adj, radius_m = build_graph(D, keep, kmed, config)

    EXPECTED_RADIUS_M = 252.06963512656085
    assert abs(radius_m - EXPECTED_RADIUS_M) < 1e-9

    edge_count = sum(len(neighbours) for neighbours in adj)
    EXPECTED_EDGE_COUNT = 2384
    assert edge_count == EXPECTED_EDGE_COUNT

    assert len(adj) == df_inliers.shape[0]


def test_clustering_snapshot(fixture_path: Path) -> None:
    df = load_raw_df(fixture_path)
    config = PipelineConfig(city="hamburg")
    df_bbox = apply_bbox(df, config)
    _x, _y, D = project_and_distance(df_bbox)
    keep, kmed = apply_knn(D, config)
    adj, _radius_m = build_graph(D, keep, kmed, config)

    comps, sizes, order, cluster_id = Clusterer.assign_from_components(adj)

    EXPECTED_N_FILTERED = 74
    EXPECTED_LARGEST_COMP_SIZE = 72
    EXPECTED_N_COMPONENTS = 2

    assert len(cluster_id) == EXPECTED_N_FILTERED
    assert len(sizes) == len(comps)
    assert len(comps) == EXPECTED_N_COMPONENTS

    largest_size = max(sizes) if sizes else 0
    assert largest_size == EXPECTED_LARGEST_COMP_SIZE