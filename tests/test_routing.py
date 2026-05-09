import numpy as np
from cm_modular.routing import AngleBiasedRouter
import numpy as np
from cm_modular.routing import AngleBiasedRouter


def test_dijkstra_plain_on_line_graph():
    # 0 --1--> 1 --1--> 2 --1--> 3
    adj = [
        [(1, 1.0)],              # 0
        [(0, 1.0), (2, 1.0)],    # 1
        [(1, 1.0), (3, 1.0)],    # 2
        [(2, 1.0)],              # 3
    ]

    dist, prev = AngleBiasedRouter.dijkstra_plain(adj, src=0)

    assert dist == [0.0, 1.0, 2.0, 3.0]

    # Reconstruct path 0 -> 3 from prev
    path = []
    node = 3
    while node != -1:
        path.append(node)
        node = prev[node]
    path.reverse()

    assert path == [0, 1, 2, 3]


def test_as_geometric_adjacency_preserves_topology_and_replaces_weights():
    adj = [
        [(1, 10.0)],             # 0
        [(0, 10.0), (2, 20.0)],  # 1
        [(1, 20.0)],             # 2
    ]

    D_base = np.array([
        [0.0, 1.0, 5.0],
        [1.0, 0.0, 2.0],
        [5.0, 2.0, 0.0],
    ])

    adj_geom = AngleBiasedRouter.as_geometric_adjacency(adj, D_base)

    # Same neighbours
    assert {j for j, _ in adj[0]} == {j for j, _ in adj_geom[0]}
    assert {j for j, _ in adj[1]} == {j for j, _ in adj_geom[1]}
    assert {j for j, _ in adj[2]} == {j for j, _ in adj_geom[2]}

    # Weights from D_base
    assert dict(adj_geom[0])[1] == D_base[0, 1]
    assert dict(adj_geom[1])[0] == D_base[1, 0]
    assert dict(adj_geom[1])[2] == D_base[1, 2]
    assert dict(adj_geom[2])[1] == D_base[2, 1]


def test_reconstruct_path_and_true_length():
    # Base distances for 0-1-2 line
    D_base = np.array([
        [0.0, 1.0, 2.0],
        [1.0, 0.0, 1.0],
        [2.0, 1.0, 0.0],
    ])

    # States (u, p): (0,-1) -> (1,0) -> (2,1)
    start_state = (0, -1)
    state_01 = (1, 0)
    state_12 = (2, 1)

    prev_state = {
        state_01: start_state,
        state_12: state_01,
    }
    end_node = 2
    last_prev = 1

    path = AngleBiasedRouter.reconstruct_path(prev_state, end_node=end_node, last_prev=last_prev)
    assert path == [0, 1, 2]

    length = AngleBiasedRouter.path_true_length_m(D_base, path)
    assert length == 2.0  # 0-1 (1.0) + 1-2 (1.0)


def test_angle_biased_router_prefers_straight_path_over_zigzag():
    # Geometry: 0 -> 1 -> 3 straight; 0 -> 2 -> 3 is an L-turn
    X = np.array([0.0, 1.0, 0.0, 1.0])
    Y = np.array([0.0, 0.0, 1.0, 1.0])

    # All edges geometric length 1.0
    adj = [
        [(1, 1.0), (2, 1.0)],  # 0
        [(0, 1.0), (3, 1.0)],  # 1
        [(0, 1.0), (3, 1.0)],  # 2
        [(1, 1.0), (2, 1.0)],  # 3
    ]

    router = AngleBiasedRouter(
        X=X,
        Y=Y,
        angle_bias_m_per_rad=10.0,  # strong turn penalty
        step_penalty_m=0.0,
        min_edge_cost_m=0.0,
    )

    best_dist_to, prev_state, best_last_prev = router.dijkstra(adj, src=0)

    # Router reports best predecessor for node 3 via the straighter path
    assert best_last_prev[3] == 1


def test_double_sweep_finds_line_endpoints():
    # 0-1-2-3-4 line, unit weights
    n = 5
    adj = [
        [(1, 1.0)],                    # 0
        [(0, 1.0), (2, 1.0)],          # 1
        [(1, 1.0), (3, 1.0)],          # 2
        [(2, 1.0), (4, 1.0)],          # 3
        [(3, 1.0)],                    # 4
    ]

    D_base = np.zeros((n, n))
    for i in range(n - 1):
        D_base[i, i + 1] = D_base[i + 1, i] = 1.0

    adj_geom = AngleBiasedRouter.as_geometric_adjacency(adj, D_base)

    # Sweep 1 from 0
    dist0, _ = AngleBiasedRouter.dijkstra_plain(adj_geom, src=0)
    a = int(np.argmax(dist0))

    # Sweep 2 from a
    dist_a, _ = AngleBiasedRouter.dijkstra_plain(adj_geom, src=a)
    b = int(np.argmax(dist_a))

    assert {a, b} == {0, 4}