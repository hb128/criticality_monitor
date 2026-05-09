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
    print(comps)
    assert len(comps) == 3
    assert sizes == [3, 3, 1]
    assert order == [1, 0, 2]
    assert np.array_equal(clusterid, [1, 1, 1, 0, 0, 0, 2])
