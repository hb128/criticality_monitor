from __future__ import annotations
import numpy as np
import pandas as pd

class RobustKNNFilter:
    """Robust outlier filter based on k-th nearest neighbor distance."""
    @staticmethod
    def keep_by_knn(D: np.ndarray, k: int = 4, n_sigmas: float = 3.0) -> tuple[np.ndarray, float]:
        """Return a boolean mask of points to keep and the median k-NN distance.

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
        """
        kth = np.partition(D, kth=k, axis=1)[:, k]
        med = float(np.median(kth))
        mad = float(np.median(np.abs(kth - med)) * 1.4826)
        thresh = med + (n_sigmas * mad if mad > 0 else 50.0)
        keep = kth <= max(30.0, thresh)
        return keep, med

class DataFilter:
    """Convenience helpers to filter a DataFrame of lat/lon points."""
    @staticmethod
    def bbox(df: pd.DataFrame, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> pd.DataFrame:
        """Return rows within the inclusive bounding box."""
        return df[df.lat.between(lat_min, lat_max) & df.lon.between(lon_min, lon_max)].copy().reset_index(drop=True)
