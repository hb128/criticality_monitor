from __future__ import annotations
import numpy as np
import pandas as pd

class RobustKNNFilter:
    """Robust outlier filter based on k-th nearest neighbor distance."""
    @staticmethod
    def keep_by_knn(D: np.ndarray, k: int = 4, n_sigmas: float = 3.0) -> tuple[np.ndarray, float]:
        """Return a boolean mask of points to keep and the median k-NN distance.
        Use a robust centre method (median) and spread (median absolute deviation) to decide which points are inliers.

        Parameters
        ----------
        D : np.ndarray
            Dense pairwise distance matrix in meters.
        k : int
            Index of the neighbor (0-based includes self at index 0). We use the k-th neighbor.
        n_sigmas : float
            Threshold in MAD units above median to keep.

        Returns
        -------
        keep : np.ndarray (n,)
            Boolean mask: True for points considered inliers.
        k_med : float
            Median k-NN distance across all points (meters).

        Notes
        -----
        The threshold for inlier selection is set to the greater of 30.0 meters or the calculated value
        (median + n_sigmas * MAD). The lower bound of 30.0 meters is chosen to avoid overly strict filtering
        in cases where the data is tightly clustered or the MAD is very small, ensuring reasonable retention
        of points in typical GPS datasets.

        If the MAD evaluates to zero (for example when many k-th neighbor distances are identical or the
        dataset is extremely uniform), a fallback additive spread of 50.0 meters is used instead of
        n_sigmas * MAD. This 50 m fallback provides a conservative, non-zero spread estimate to avoid a
        degenerate threshold that would otherwise exclude most points; it makes the filter robust when the
        observed variability is numerically zero or too small to be useful.
        """
        kth = np.partition(D, kth=k, axis=1)[:, k]
        median = float(np.median(kth))
        mad = float(np.median(np.abs(kth - median)) * 1.4826) # median absolute deviation, scaling to be comparable to std of Gaussian
        thresh = median + (n_sigmas * mad if mad > 0 else 50.0)
        keep = kth <= max(30.0, thresh)
        return keep, median

class DataFilter:
    """Convenience helpers to filter a DataFrame of lat/lon points."""
    @staticmethod
    def bbox(df: pd.DataFrame, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> pd.DataFrame:
        """Return rows within the inclusive bounding box."""
        return df[df.lat.between(lat_min, lat_max) & df.lon.between(lon_min, lon_max)].copy().reset_index(drop=True)
