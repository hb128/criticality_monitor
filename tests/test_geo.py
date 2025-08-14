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
