import numpy as np
from cm_modular.graphing import GraphBuilder

def test_build_graph_penalty_applied():
    # Adjusted points: 0 --(10m)-- 1 --(70m)-- 2 (all within connection radius)
    D = np.array([[0.0, 10.0, 70.0],
                  [10.0, 0.0, 60.0],
                  [70.0, 60.0, 0.0]])
    adj, r = GraphBuilder.build_graph(D, k_med=50.0, L0=50.0, penalty_factor=3.0)
    # Verify adjacency list includes all expected connections
    # Node 0 should connect to Node 1 with cost 10.0 and to Node 2 with penalized cost (70.0 + 3.0 * 20.0)
    assert len(adj[0]) == 2 and (1, 10.0) in adj[0] and (2, 70.0 + 3.0 * 20.0) in adj[0]
    # Node 1 should connect to Node 0 with cost 10.0 and to Node 2 with penalized cost (60.0 + 3.0 * 10.0)
    assert len(adj[1]) == 2 and (0, 10.0) in adj[1] and (2, 60.0 + 3.0 * 10.0) in adj[1]
    # Node 2 should connect to Node 0 with penalized cost (70.0 + 3.0 * 20.0) and to Node 1 with penalized cost (60.0 + 3.0 * 10.0)
    assert len(adj[2]) == 2 and (0, 70.0 + 3.0 * 20.0) in adj[2] and (1, 60.0 + 3.0 * 10.0) in adj[2]
