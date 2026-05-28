from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from matplotlib.figure import Figure

class GraphPlotter:
    @staticmethod
    def plot_graph(
        filtered: pd.DataFrame,
        adj: List[List[Tuple[int, float]]],
        D_f: np.ndarray,
        *,
        cost_mode: str = "adj",  # "adj" or "geom"
        path_indices: Optional[list[int]] = None,
        router: Optional[object] = None,
        title: Optional[str] = None,
        figsize: Tuple[float, float] = (9.0, 6.0),
    ) -> Figure:
        """
        Create a graph visualization (pure function - returns Figure, no file IO).
        
        Returns:
            matplotlib.figure.Figure: The generated plot
        """
        assert "lon" in filtered.columns and "lat" in filtered.columns, "filtered must include lon/lat"
        lons = filtered["lon"].to_numpy()
        lats = filtered["lat"].to_numpy()

        # Unique edges
        segments = []
        costs = []
        seen = set()
        for i, nbrs in enumerate(adj):
            for j, w in nbrs:
                key = (i, j) if i < j else (j, i)
                if key in seen:
                    continue
                seen.add(key)
                segments.append([(lons[i], lats[i]), (lons[j], lats[j])])
                costs.append(float(D_f[i, j]) if cost_mode == "geom" else float(w))
        costs = np.asarray(costs) if segments else np.array([])

        fig, ax = plt.subplots(figsize=figsize)

        if segments:
            lc = LineCollection(segments, cmap="viridis",
                                norm=Normalize(vmin=float(costs.min()), vmax=float(costs.max())))
            lc.set_array(costs)
            lc.set_linewidth(1.5)
            lc.set_alpha(0.8)
            ax.add_collection(lc)
            cbar = fig.colorbar(lc, ax=ax, shrink=0.85)
            cbar.set_label("edge cost ({})".format("geom meters" if cost_mode == "geom" else "adj weight"))

        # Nodes
        ax.scatter(lons, lats, s=10, c="#111111", zorder=3)

        ax.set_xlabel("longitude")
        ax.set_ylabel("latitude")
        ax.set_title(title or f"Graph ({cost_mode} costs)")
        ax.set_aspect("equal")
        ax.margins(0.02)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig