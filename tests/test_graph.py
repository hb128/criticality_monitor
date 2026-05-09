import numpy as np
from cm_modular.graphing import GraphBuilder

def test_build_graph_radius_clamped_to_expected_range():
    # Distances chosen so all edges are within any plausible radius
    D = np.array([[0.0, 10.0, 20.0],
                  [10.0, 0.0, 15.0],
                  [20.0, 15.0, 0.0]])

    # Case 1: small kmed → lower bound 30 m
    adj_small, r_small = GraphBuilder.build_graph(D, k_med=5.0, L0=50.0, penalty_factor=3.0)
    assert 29.9 < r_small < 30.1  # approx 30 m
    # All edges are < 30 -> fully connected graph
    assert all(len(neighs) == 2 for neighs in adj_small)

    # Case 2: medium kmed → 1.6 * kmed in range
    adj_mid, r_mid = GraphBuilder.build_graph(D, k_med=50.0, L0=50.0, penalty_factor=3.0)
    assert 79.0 < r_mid < 81.0  # 1.6 * 50 = 80
    # Same connectivity, but checking radius is taken from kmed

    # Case 3: large kmed → upper bound 300 m
    adj_large, r_large = GraphBuilder.build_graph(D, k_med=1000.0, L0=50.0, penalty_factor=3.0)
    assert 299.0 < r_large < 301.0  # approx 300 m

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


def test_build_graph_symmetric_and_no_self_loops():
    D = np.array([[0.0, 10.0, 20.0],
                  [10.0, 0.0, 25.0],
                  [20.0, 25.0, 0.0]])

    adj, r = GraphBuilder.build_graph(D, k_med=20.0, L0=50.0, penalty_factor=3.0)

    n = D.shape[0]

    # No self-loops
    for i in range(n):
        for j, cost in adj[i]:
            assert j != i

    # Symmetric adjacency: if j is in adj[i], then i is in adj[j] with same cost
    for i in range(n):
        for j, cost_ij in adj[i]:
            neighbours_j = dict(adj[j])
            assert i in neighbours_j
            assert neighbours_j[i] == cost_ij


def test_angle_bias_for_segment_first_segment_is_one():
    # Simple path with at least two segments
    xf = np.array([0.0, 1.0, 2.0])
    yf = np.array([0.0, 0.0, 0.0])
    path = [0, 1, 2]

    factor0 = GraphBuilder.angle_bias_for_segment(xf, yf, path, 0)
    assert factor0 == 1.0


def test_angle_bias_for_segment_increases_on_turn():
    # Path that turns 90 degrees at node 1: (0,0) -> (1,0) -> (1,1)
    xf = np.array([0.0, 1.0, 1.0])
    yf = np.array([0.0, 0.0, 1.0])
    path = [0, 1, 2]

    # First segment: straight, no previous direction
    factor0 = GraphBuilder.angle_bias_for_segment(xf, yf, path, 0)
    # Second segment: turn at node 1, should incur a penalty >= 1.0
    factor1 = GraphBuilder.angle_bias_for_segment(xf, yf, path, 1)

    assert factor0 == 1.0
    assert factor1 >= 1.0
    # Ideally, a turn should not get rewarded, so strictly greater:
    assert factor1 > factor0