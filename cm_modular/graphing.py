from __future__ import annotations
from typing import List, Tuple
import numpy as np

class GraphBuilder:
    """Build adjacency graphs and connected components."""
    @staticmethod
    def build_graph(D: np.ndarray, k_med: float, L0: float = 50.0, penalty_factor: float = 0.0) -> tuple[list[list[tuple[int, float]]], float]:
        """Build an adjacency list from distances with a soft penalty for long edges.

        The penalty is applied to the edge *cost* (not geometric length) to discourage long jumps,
        while the true geometric distance remains available from D when needed.

        Parameters
        ----------
        D : np.ndarray
            Pairwise distances in meters.
        k_med : float
            Median k-NN distance from the robust filter (used to derive connection radius).
        L0 : float
            Threshold in meters after which an extra linear penalty applies.
        penalty_factor : float
            Extra cost per meter beyond L0 (meters of cost per meter length).

        Returns
        -------
        (adj, r) : (list, float)
            Adjacency list and the connection radius used.
        """
        r = float(min(300.0, max(30.0, 1.6 * k_med)))
        n = D.shape[0]
        adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if D[i, j] <= r:
                    length = float(D[i, j])
                    cost = length
                    if length > L0:
                        cost += penalty_factor * (length - L0)
                    adj[i].append((j, cost))
        return adj, r

    @staticmethod
    def components(adj: list[list[tuple[int, float]]]) -> list[list[int]]:
        """Compute weakly-connected components for a directed adjacency list (treated as undirected)."""
        n = len(adj)
        seen = [False] * n
        comps: list[list[int]] = []
        for i in range(n):
            if seen[i]:
                continue
            stack = [i]; seen[i] = True; nodes = [i]
            while stack:
                u = stack.pop()
                for v, _ in adj[u]:
                    if not seen[v]:
                        seen[v] = True
                        stack.append(v)
                        nodes.append(v)
            comps.append(nodes)
        return comps
