import numpy as np
from cm_modular.clustering import Clusterer

def test_two_components_detected():
    # Triangle 1: 0-1-2
    # Triangle 2: 3-4-5  
    # Isolated: 6
    adj = [
        [(1, 0.0), (2, 0.0)],  # 0 connects to 1, 2
        [(0, 0.0), (2, 0.0)],  # 1 connects to 0, 2
        [(0, 0.0), (1, 0.0)],  # 2 connects to 0, 1
        [(4, 0.0), (5, 0.0)],  # 3 connects to 4, 5
        [(3, 0.0), (5, 0.0)],  # 4 connects to 3, 5
        [(3, 0.0), (4, 0.0)],  # 5 connects to 3, 4
        []                      # 6 is isolated
    ]
    
    comps, sizes, order, clusterid = Clusterer.assign_from_components(adj)
    
    # Your assertions here
    assert len(comps) == 3
    assert sizes == [3, 3, 1]
    assert order == [1, 0, 2]
    assert np.array_equal(clusterid, [1, 1, 1, 0, 0, 0, 2])


def test_largest_component_gets_cluster_id_zero():
    # Component A: nodes 0-1-2 (size 3)
    # Component B: nodes 3-4 (size 2)
    adj = [
        [(1, 0.0), (2, 0.0)],  # 0
        [(0, 0.0), (2, 0.0)],  # 1
        [(0, 0.0), (1, 0.0)],  # 2
        [(4, 0.0)],            # 3
        [(3, 0.0)],            # 4
    ]

    comps, sizes, order, clusterid = Clusterer.assign_from_components(adj)

    # We expect two components: sizes 3 and 2
    assert len(comps) == 2
    assert sorted(sizes, reverse=True) == [3, 2]

    # Largest component gets cluster id 0
    largest_comp_index = order[0]
    largest_nodes = comps[largest_comp_index]
    for node in largest_nodes:
        assert clusterid[node] == 0

    # Smaller component must have a cluster id > 0
    smaller_comp_index = order[1]
    smaller_nodes = comps[smaller_comp_index]
    for node in smaller_nodes:
        assert clusterid[node] > 0


def test_isolated_node_is_own_component():
    # One edge 0-1, and one isolated node 2
    adj = [
        [(1, 0.0)],  # 0
        [(0, 0.0)],  # 1
        [],          # 2 isolated
    ]

    comps, sizes, order, clusterid = Clusterer.assign_from_components(adj)

    # Expect 2 components: one of size 2 (nodes 0,1) and one of size 1 (node 2)
    assert len(comps) == 2
    assert sorted(sizes, reverse=True) == [2, 1]

    # Find the isolated component
    isolated_comp_index = sizes.index(1)
    isolated_nodes = comps[isolated_comp_index]
    assert isolated_nodes == [2]

    # clusterid[2] must be a valid rank (0 or 1 depending on which component is larger)
    assert clusterid[2] in (0, 1)
    # And 2 must not appear in any other component
    assert all(2 not in c for i, c in enumerate(comps) if i != isolated_comp_index)