from pathlib import Path

from cm_modular.pipeline import PipelineConfig, Pipeline

import pytest


@pytest.fixture
def fixture_path() -> Path:
    # Adjust name to your actual anonymised fixture filename
    return Path("tests/fixtures/hamburg_ride_small.json")

@pytest.fixture
def sparse_fixture_path() -> Path:
    return Path("tests/fixtures/hamburg_ride_sparse.json")

def test_snapshot_full_run(tmp_path: Path, fixture_path: Path) -> None:
    # Arrange
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