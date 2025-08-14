from __future__ import annotations
import numpy as np

class Clusterer:
    """Assign sequential cluster ids (0=largest) from components."""
    @staticmethod
    def assign_from_components(adj: list[list[tuple[int,float]]]) -> tuple[list[list[int]], list[int], list[int], np.ndarray]:
        """Return components, sizes, order (largest-first), and a cluster_id array."""
        n = len(adj)
        # Build components treating graph as undirected
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
        sizes = [len(c) for c in comps]
        order = np.argsort(sizes)[::-1].tolist()
        cluster_id = np.full(n, -1, dtype=int)
        for rank, comp_idx in enumerate(order):
            for node in comps[comp_idx]:
                cluster_id[node] = rank
        return comps, sizes, order, cluster_id
