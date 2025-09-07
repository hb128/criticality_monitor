from __future__ import annotations
import numpy as np

class Clusterer:
    """Assign sequential cluster ids (0=largest) from components."""
    @staticmethod
    def assign_from_components(adj: list[list[tuple[int,float]]]) -> tuple[list[list[int]], list[int], list[int], np.ndarray]:
        """
        Find connected components in a graph given as an adjacency list and return
        convenient summaries for downstream processing.

        The function treats the supplied adjacency list as an undirected connectivity
        relation (i.e. connectivity is determined by traversing outgoing edges).
        For graphs produced by the project's GraphBuilder the adjacency is symmetric
        (both i->j and j->i present), so this routine yields the weakly connected
        components.

        Parameters
        ----------
        adj : list[list[tuple[int, float]]]
            Directed adjacency list where adj[i] is a list of (neighbor_index, weight).
            Only the neighbor indices are used for connectivity; weights are ignored.

        Returns
        -------
        comps : list[list[int]]
            List of components, each component is a list of node indices. The nodes
            inside a component appear in the order they were discovered by the DFS
            stack traversal (not sorted).
        sizes : list[int]
            Parallel list of component sizes (len of each component), same order as `comps`.
        order : list[int]
            List of component indices sorted by component size in descending order.
            `order[0]` is the index in `comps` of the largest component.
        cluster_id : np.ndarray (shape (n,))
            Integer array mapping node index -> cluster rank, where 0 denotes the
            largest component, 1 the second largest, etc. Nodes not present would be -1
            (shouldn't happen with valid adjacency of length n).

        Notes
        -----
        - The algorithm performs a depth-first traversal using an explicit stack.
          Time complexity is O(n + m) where n is number of nodes and m is number of edges.
        - The routine ignores edge weights and only uses topology to compute components.
        - The ordering inside each component depends on traversal order; do not rely
          on any particular ordering of nodes within a component.
        - The returned `cluster_id` is convenient for colouring/labeling nodes such that
          rank 0 corresponds to the largest cluster.

        Example
        -------
        >>> adj = [
        ...     [(1,1.0)],
        ...     [(0,1.0),(2,1.0)],
        ...     [(1,1.0)]
        ... ]
        >>> comps, sizes, order, cid = Clusterer.assign_from_components(adj)
        >>> comps  # all three nodes in a single component
        [[0,1,2]]
        >>> sizes
        [3]
        >>> order
        [0]
        >>> cid.tolist()
        [0,0,0]
        """
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
