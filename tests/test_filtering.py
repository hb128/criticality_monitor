import numpy as np
import pandas as pd
from cm_modular.filtering import RobustKNNFilter, DataFilter

def test_bbox_filters_rows_and_resets_index():
    df = pd.DataFrame(
        {
            "lat": [53.0, 53.5, 54.0],
            "lon": [10.0, 10.1, 10.2],
            "val": [1, 2, 3],
        }
    )

    lat_min, lat_max = 53.2, 54.0
    lon_min, lon_max = 10.05, 10.25

    filtered = DataFilter.bbox(df, lat_min, lat_max, lon_min, lon_max)

    # Only last two rows should remain
    assert len(filtered) == 2
    assert filtered["val"].tolist() == [2, 3]
    # Index must be reset
    assert list(filtered.index) == [0, 1]

    
def test_knnfilter_removes_isolated_point():
    # 9 points in a tight cluster around (0,0) and 1 far outlier at (1000, 0)
    cluster = np.zeros((9, 2))
    outlier = np.array([[1000.0, 0.0]])
    pts = np.vstack([cluster, outlier])

    # Build distance matrix
    D = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(axis=2))

    k = 3
    nsigmas = 3.0

    keep, kmed = RobustKNNFilter.keep_by_knn(D, k, nsigmas)

    # We expect 9 inliers and 1 outlier (the last point)
    assert keep.shape == (10,)
    assert keep.sum() == 9
    assert not keep[-1]


def test_knnfilter_does_not_overfilter_dense_cluster():
    # 4x4 grid of points with spacing 1.0
    xs, ys = np.meshgrid(np.arange(4), np.arange(4))
    pts = np.column_stack([xs.ravel(), ys.ravel()])

    D = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(axis=2))

    k = 3
    nsigmas = 3.0

    keep, kmed = RobustKNNFilter.keep_by_knn(D, k, nsigmas)

    # All points are in a uniform dense cluster; none should be rejected
    assert keep.shape == (16,)
    assert keep.all()


def test_knnfilter_mad_zero_fallback_does_not_crash():
    # All pairwise distances identical (except diagonal)
    n = 5
    D = np.full((n, n), 10.0, dtype=float)
    np.fill_diagonal(D, 0.0)

    k = 2
    nsigmas = 3.0

    keep, kmed = RobustKNNFilter.keep_by_knn(D, k, nsigmas)

    # The important thing: no exception, mask shape is correct
    assert keep.shape == (n,)
    # With identical distances, either all kept or all rejected, but consistent
    assert (keep.all() or (~keep).all())
    assert isinstance(kmed, float)

