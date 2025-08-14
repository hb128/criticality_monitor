import numpy as np
from cm_modular.graphing import GraphBuilder

def test_build_graph_penalty_applied():
    # Simple 3-node line: 0 --(10m)-- 1 --(100m)-- 2
    D = np.array([[0.0, 10.0, 110.0],
                  [10.0, 0.0, 100.0],
                  [110.0, 100.0, 0.0]])
    adj, r = GraphBuilder.build_graph(D, k_med=50.0, L0=50.0, penalty_factor=3.0)
    # Edge (1->2) length 100 > L0 => cost 100 + 3*(100-50) = 250
    cost_1_2 = next(c for v,c in adj[1] if v==2)
    assert abs(cost_1_2 - 250.0) < 1e-9
