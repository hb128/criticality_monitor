import numpy as np
from cm_modular.geo import GeoUtils

def test_deg2meters_roundtrip_dimensions():
    lat = np.array([53.5, 53.5001, 53.5002])
    lon = np.array([10.0, 10.0001, 10.0002])
    x, y = GeoUtils.deg2meters(lat, lon)
    assert x.shape == lat.shape
    assert y.shape == lon.shape
    D = GeoUtils.pairwise_xy(x, y)
    assert D.shape == (3,3)
    # Distance from point 0 to itself is 0
    assert abs(D[0,0]) < 1e-9
    # Symmetry
    assert np.allclose(D, D.T, atol=1e-9)

def test_pairwise_xy_known_distances_3_4_5_triangle():
    x = np.array([0, 1, 0])
    y = np.array([0, 0, 1])
    D = GeoUtils.pairwise_xy(x, y)
    assert D.shape == (3,3)
    assert abs(D[0, 0]) < 1e-9
    assert D[0, 1] == D[1, 0]
    assert abs(D[0, 1] - 1) < 1e-9
    assert abs(D[0, 2] - 1) < 1e-9
    assert abs(D[1, 2] - np.sqrt(2)) < 1e-9
    
def test_deg2meters_uses_median_reference_when_none():
    lat = np.array([53.0, 54.0, 55.0])
    lon = np.array([10.0, 11.0, 12.0])

    # With explicit median reference
    lat0_explicit = np.median(lat)
    lon0_explicit = np.median(lon)
    x_explicit, y_explicit = GeoUtils.deg2meters(lat, lon, lat0_explicit, lon0_explicit)

    # With None → should internally choose the same median reference
    x_auto, y_auto = GeoUtils.deg2meters(lat, lon)

    assert x_auto.shape == x_explicit.shape
    assert y_auto.shape == y_explicit.shape
    assert np.allclose(x_auto, x_explicit)
    assert np.allclose(y_auto, y_explicit)

def test_deg2meters_preserves_shape():
    lat = np.array([[53.0, 53.1], [53.2, 53.3]])
    lon = np.array([[10.0, 10.1], [10.2, 10.3]])

    x, y = GeoUtils.deg2meters(lat, lon)

    assert x.shape == lat.shape
    assert y.shape == lon.shape

def test_deg2meters_uses_reasonable_earth_radius_scale():
    # Two points differing by 1° latitude only
    lat = np.array([0.0, 1.0])
    lon = np.array([0.0, 0.0])

    x, y = GeoUtils.deg2meters(lat, lon, lat0=0.0, lon0=0.0)

    dy = y[1] - y[0]
    # 1 degree of latitude ≈ 111.2 km on Earth
    assert 100_000.0 < dy < 120_000.0

def test_deg2meters_reasonable_for_city_scale():
    # ~10 km box around Hamburg
    lat = np.array([53.55, 53.60])
    lon = np.array([9.90, 10.00])

    x, y = GeoUtils.deg2meters(lat, lon)

    distance = np.hypot(x[1] - x[0], y[1] - y[0])
    # Distance should be in a plausible city-scale range (a few km to ~20 km)
    assert 1_000.0 < distance < 30_000.0
