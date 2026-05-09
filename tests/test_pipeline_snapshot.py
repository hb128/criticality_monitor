from pathlib import Path

import pytest

from cm_modular.pipeline import PipelineConfig, Pipeline
from cm_modular.io import DataLoader
from cm_modular.filtering import DataFilter


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fixture_path() -> Path:
    """Full-run fixture: small Hamburg ride."""
    return Path("tests/fixtures/hamburg_ride_small.json")


@pytest.fixture
def sparse_fixture_path() -> Path:
    """Sparse fixture: triggers early-exit branch in compute."""
    return Path("tests/fixtures/hamburg_ride_sparse.json")


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

    # Structural: keys must exist
    for key in EXPECTED:
        assert key in metrics

    # Exact integer counts
    assert metrics["n_points"] == EXPECTED["n_points"]
    assert metrics["n_bbox"] == EXPECTED["n_bbox"]
    assert metrics["n_filtered"] == EXPECTED["n_filtered"]
    assert metrics["largest_comp_size"] == EXPECTED["largest_comp_size"]

    # Floats with tolerance
    assert abs(metrics["connection_radius_m"] - EXPECTED["connection_radius_m"]) < 1e-6
    assert abs(metrics["length_m"] - EXPECTED["length_m"]) < 1e-6


def test_sparse_input_does_not_crash(tmp_path: Path, sparse_fixture_path: Path) -> None:
    config = PipelineConfig(city="hamburg")
    pipeline = Pipeline(config)
    pipeline.add_files([str(sparse_fixture_path)])

    out_html = tmp_path / "out.html"

    _folium_map, html_path, metrics = pipeline.run(
        out_html=str(out_html),
        return_metrics=True,
    )

    # Sanity: still writes HTML
    assert html_path == out_html
    assert out_html.exists()

    # Early-exit behaviour snapshot
    assert metrics["length_m"] == 0.0
    assert metrics["n_filtered"] == 9


# --- Per-stage integration snapshots ---------------------------------------


def test_dataloader_snapshot(fixture_path: Path) -> None:
    # Act: load the single JSON via the real loader
    df = DataLoader.load_multiple_locations_json([str(fixture_path)])

    # Snapshot: shape, columns, first timestamp
    EXPECTED_N_ROWS = 446
    EXPECTED_COLUMNS = ["id", "lat", "lon", "timestamp"]
    EXPECTED_FIRST_TS = 1758915587

    assert df.shape[0] == EXPECTED_N_ROWS
    assert list(df.columns) == EXPECTED_COLUMNS

    # First timestamp snapshot (after sorting)
    first_ts = df["timestamp"].iloc[0]
    assert first_ts == EXPECTED_FIRST_TS


def test_bbox_snapshot(fixture_path: Path) -> None:
    # Arrange: load raw data
    df = DataLoader.load_multiple_locations_json([str(fixture_path)])

    # Use the same config the pipeline uses to get bbox
    config = PipelineConfig(city="hamburg")
    lat_min, lat_max = config.lat_min, config.lat_max
    lon_min, lon_max = config.lon_min, config.lon_max

    # Act: apply bbox filter
    filtered = DataFilter.bbox(df, lat_min, lat_max, lon_min, lon_max)

    # Snapshot expectations (taken from full-run metrics)
    EXPECTED_N_BBOX = 109

    assert filtered.shape[0] == EXPECTED_N_BBOX

    # Optional sanity: all points inside bbox
    assert (filtered["lat"] >= lat_min).all()
    assert (filtered["lat"] <= lat_max).all()
    assert (filtered["lon"] >= lon_min).all()
    assert (filtered["lon"] <= lon_max).all()