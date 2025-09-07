from __future__ import annotations
from typing import List, Tuple, Optional
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize

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
        out: Optional[str | None] = None,
        figsize: Tuple[float, float] = (9.0, 6.0),
    ):
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

        # # Optional: overlay path with per-step costs (no step/angle penalties)
        # if path_indices and len(path_indices) >= 2:
        #     path_segs, path_costs = [], []
        #     for k in range(len(path_indices) - 1):
        #         u, v = path_indices[k], path_indices[k + 1]
        #         path_segs.append([(lons[u], lats[u]), (lons[v], lats[v])])
        #         # Use raw edge cost only: geometric if requested, otherwise adjacency weight
        #         base_w = float(D_f[u, v]) if cost_mode == "geom" else next((float(w) for (j, w) in adj[u] if j == v), float(D_f[u, v]))
        #         path_costs.append(base_w)
        #     path_costs = np.asarray(path_costs)
        #     plc = LineCollection(path_segs, cmap="plasma",
        #                          norm=Normalize(vmin=float(path_costs.min()), vmax=float(path_costs.max())))
        #     plc.set_array(path_costs)
        #     plc.set_linewidth(3.0)
        #     plc.set_alpha(0.95)
        #     ax.add_collection(plc)
        #     pcbar = fig.colorbar(plc, ax=ax, shrink=0.85)
        #     pcbar.set_label("path edge cost (raw)")
        ax.set_xlabel("longitude")
        ax.set_ylabel("latitude")
        ax.set_title(title or f"Graph ({cost_mode} costs)")
        ax.set_aspect("equal")
        ax.margins(0.02)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        if out:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(out, dpi=150)
            print(f"Saved graph plot to {out}")
            plt.close(fig)
        else:
            plt.show()
        return fig