from __future__ import annotations
import numpy as np

class GeoUtils:
    """Geospatial helper utilities."""
    @staticmethod
    def deg2meters(lat: np.ndarray, lon: np.ndarray, lat0: float | None = None, lon0: float | None = None):
        """Convert latitude/longitude (degrees) to local planar meters.

        Uses a simple equirectangular approximation around (lat0, lon0).

        Parameters
        ----------
        lat, lon : np.ndarray
            Latitude and longitude in degrees.
        lat0, lon0 : float | None
            Optional reference point (degrees). If None, uses medians of inputs.

        Returns
        -------
        (x, y) : tuple[np.ndarray, np.ndarray]
            Planar coordinates in meters with the origin near the data centroid.
        """
        if lat0 is None:
            lat0 = float(np.median(lat))
        if lon0 is None:
            lon0 = float(np.median(lon))
        R = 6371000.0
        x = np.deg2rad(lon - lon0) * R * np.cos(np.deg2rad(lat0))
        y = np.deg2rad(lat - lat0) * R
        return x, y

    @staticmethod
    def pairwise_xy(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
        """Compute dense pairwise Euclidean distances for coordinates in meters.

        Parameters
        ----------
        X, Y : np.ndarray
            Arrays of equal length with x/y positions in meters.

        Returns
        -------
        D : np.ndarray (n, n)
            Matrix of distances in meters.
        """
        P = np.column_stack([X, Y])
        n = len(P)
        D = np.empty((n, n), dtype=float)
        for i in range(n):
            dx = P[:, 0] - P[i, 0]
            dy = P[:, 1] - P[i, 1]
            D[i] = np.hypot(dx, dy)
        return D
