from __future__ import annotations
from typing import Dict, Tuple, List
import math, heapq
import numpy as np

class AngleBiasedRouter:
    """Expanded-state Dijkstra that penalizes turns and per-edge steps.

    The algorithm uses states (node=u, prev=p) and sets the transition cost to:
        cost = max(w, min_edge_cost_m)  +  step_penalty_m  +  angle_bias_m_per_rad * turn_angle(p,u,v)
    where w is the graph edge weight.

    Use :meth:`path_true_length_m` to compute the unpenalized geometric length afterwards.
    """

    def __init__(self, X: np.ndarray, Y: np.ndarray,
                 angle_bias_m_per_rad: float = 8.0,
                 step_penalty_m: float = 5.0,
                 min_edge_cost_m: float = 15.0):
        self.X = X
        self.Y = Y
        self.angle_bias_m_per_rad = float(angle_bias_m_per_rad)
        self.step_penalty_m = float(step_penalty_m)
        self.min_edge_cost_m = float(min_edge_cost_m)

    @staticmethod
    def _heading(i: int, j: int, X: np.ndarray, Y: np.ndarray) -> float:
        return math.atan2(Y[j] - Y[i], X[j] - X[i])

    @staticmethod
    def _turn_angle(p: int, u: int, v: int, X: np.ndarray, Y: np.ndarray) -> float:
        if p == -1:
            return 0.0
        a1 = math.atan2(Y[u] - Y[p], X[u] - X[p])
        a2 = math.atan2(Y[v] - Y[u], X[v] - X[u])
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        return abs(da)

    def dijkstra(self, adj: list[list[tuple[int, float]]], src: int):
        """Run expanded-state Dijkstra from a source node.

        Returns
        -------
        best_dist_to : list[float]
            Best known cost to reach each node (aggregating over previous state).
        prev_state : dict[tuple[int,int], tuple[int,int]]
            Backpointers map for full state reconstruction.
        best_last_prev : list[int]
            The 'prev' that yielded the best_dist_to at each end node.
        """
        INF = 1e30
        dist: Dict[tuple[int,int], float] = {}
        prev_state: Dict[tuple[int,int], tuple[int,int]] = {}
        best_dist_to = [INF] * len(adj)
        best_last_prev = [-1] * len(adj)

        start = (src, -1)
        dist[start] = 0.0
        best_dist_to[src] = 0.0
        pq: list[tuple[float,int,int]] = [(0.0, src, -1)]

        while pq:
            d, u, p = heapq.heappop(pq)
            state = (u, p)
            if d != dist.get(state, INF):
                continue
            for v, w in adj[u]:
                base = max(w, self.min_edge_cost_m)
                penalty = self.step_penalty_m + self.angle_bias_m_per_rad * self._turn_angle(p, u, v, self.X, self.Y)
                nd = d + base + penalty
                nxt = (v, u)
                if nd < dist.get(nxt, INF) - 1e-9:
                    dist[nxt] = nd
                    prev_state[nxt] = state
                    heapq.heappush(pq, (nd, v, u))
                    if nd < best_dist_to[v] - 1e-9:
                        best_dist_to[v] = nd
                        best_last_prev[v] = u
        return best_dist_to, prev_state, best_last_prev

    def dijkstra_plain(adj: list[list[tuple[int, float]]], src: int):
        """Standard Dijkstra on adjacency `adj` using the provided edge weights.

        This ignores turn/step/long-edge penalties entirely. Use it when you want
        distances under *pure* edge costs (e.g., geometric meters), typically by
        passing an adjacency where each edge weight is D_base[i, j].

        Parameters
        ----------
        adj : list[list[tuple[int, float]]]
            Adjacency list where `adj[u]` is a list of `(v, w)` pairs.
        src : int
            Source node index.

        Returns
        -------
        dist : list[float]
            Best-known cost from `src` to each node.
        prev : list[int]
            Backpointer (parent) for path reconstruction under this metric.
        """
        import heapq
        INF = 1e30
        n = len(adj)
        dist = [INF] * n
        prev = [-1] * n
        dist[src] = 0.0
        pq: list[tuple[float, int]] = [(0.0, src)]

        while pq:
            d, u = heapq.heappop(pq)
            if d != dist[u]:
                continue
            for v, w in adj[u]:
                nd = d + w
                if nd < dist[v] - 1e-9:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, prev


    def as_geometric_adjacency(adj: list[list[tuple[int, float]]], D_base) -> list[list[tuple[int, float]]]:
        """Return a copy of `adj` with each weight replaced by the geometric distance `D_base[i, j]`.

        Useful to run `dijkstra_plain` on the same connectivity but with *true* (unpenalized)
        edge costs.
        """
        G = []
        for i, nbrs in enumerate(adj):
            G.append([(j, float(D_base[i, j])) for (j, _w) in nbrs])
        return G


    @staticmethod
    def reconstruct_path(prev_state: Dict[tuple[int,int], tuple[int,int]], end_node: int, last_prev: int) -> list[int]:
        """Reconstruct a node path using state backpointers."""
        path_states = []
        cur = (end_node, last_prev)
        while cur in prev_state:
            path_states.append(cur)
            cur = prev_state[cur]
        path_states.append(cur)  # (src, -1)
        path_states.reverse()
        nodes = [path_states[0][0]]
        for st in path_states[1:]:
            nodes.append(st[0])
        return nodes

    @staticmethod
    def path_true_length_m(D_base: np.ndarray, path: list[int]) -> float:
        """Compute the unpenalized geometric length of a node path using D_base."""
        if len(path) < 2:
            return 0.0
        return float(sum(D_base[path[i], path[i+1]] for i in range(len(path) - 1)))
